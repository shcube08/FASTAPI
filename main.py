from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import FastAPI, Depends, HTTPException, UploadFile, Form
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey,MetaData
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import List
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.responses import FileResponse
import secrets
import os
from dotenv import load_dotenv
from fastapi import BackgroundTasks
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import BaseModel
import logging

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
app = FastAPI()
load_dotenv()


DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, unique=True)
    password = Column(String)  

    files = relationship("File", back_populates="owner")

class File(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    original_filename = Column(String)
    expiry_date = Column(DateTime, nullable=True)  
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    owner = relationship("User", back_populates="files")


class UserBase(BaseModel):
    id: int
    username: str
    password: str

class FileBase(BaseModel):
    id: int
    filename: str
    original_filename: str
    expiry_date: datetime
    owner_id: int


class UserCreate(BaseModel):
    username: str
    password: str


Base.metadata.create_all(bind=engine, tables=[User.__table__, File.__table__])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = "HS256"


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Password hashing
class Password:
    def __init__(self, rounds: int = 12):
        self.rounds = rounds
        self._context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash(self, password: str) -> str:
        return self._context.hash(password)

    def verify(self, password: str, hashed_password: str) -> bool:
        return self._context.verify(password, hashed_password)

password_handler = Password()



def create_token(data: dict, expires_delta: timedelta = None):  # Use timedelta
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)  # Use timedelta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def delete_expired_files(db: Session):
    try:
        expired_files = db.query(File).filter(File.expiry_date <= datetime.utcnow()).all()
        for file in expired_files:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename + os.path.splitext(file.original_filename)[1])
            if os.path.exists(file_path):
                os.remove(file_path)
            db.delete(file)
        db.commit()
    finally:
        db.close()


# Function to start the scheduler
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(delete_expired_files, trigger=IntervalTrigger(minutes=60), args=[SessionLocal()])  # Adjust the interval as needed
    scheduler.start()

# Registration endpoint
@app.post("/register")
def register(user_create: UserCreate, db: Session = Depends(get_db)):
    hashed_password = password_handler.hash(user_create.password)
    db_user = User(username=user_create.username, password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": "User registered successfully"}

# Login endpoint
@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(form_data.username, form_data.password, db=db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {"sub": user.username}
    access_token = create_token(token_data)
    return {"access_token": access_token, "token_type": "bearer"}



# Route for handling file uploads
def authenticate_user(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    logging.info("User from authenticate_user: %s", user)
    if user and password_handler.verify(password, user.password):
        return user
    return None

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    #print("Received token:", token)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        #print("Decoded payload:", payload)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception

    return user

def generate_unique_code():
    return secrets.token_hex(8)  # Adjust the length as needed

UPLOAD_FOLDER = "C:\\src\\FASTapi\\folder"

@app.post("/upload-file")
def upload_file_route(
    file: UploadFile = UploadFile(...),
    expiry_date: datetime = Form(...),
    current_user: User = Depends(get_current_user),  
    db: Session = Depends(get_db)
):
      
    try:
        expiry_minutes = int(expiry_date.timestamp() - datetime.utcnow().timestamp()) / 60
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid expiry_date format",
        )
    file_code = generate_unique_code()
    file_path = os.path.join(UPLOAD_FOLDER, file_code + os.path.splitext(file.filename)[1])

    
    logging.info("Saving file to path: %s", file_path)
    

    
    with open(file_path, "wb") as f:
        f.write(file.file.read())

    
    logging.info("File saved successfully")
    # Create a new record in the database
    db_file = File(
        filename=file_code,
        original_filename=file.filename,
        expiry_date=datetime.utcnow() + timedelta(minutes=expiry_minutes),
        owner_id=current_user.id,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return {"file_code": file_code, "expiry_date": db_file.expiry_date}

@app.get("/download-file/{file_code}")
def download_file_route(file_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    file = db.query(File).filter(File.filename == file_code).first()

    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    file_path = os.path.join(UPLOAD_FOLDER, file_code + os.path.splitext(file.original_filename)[1])

    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if file.expiry_date and file.expiry_date < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File has expired")

    return FileResponse(path=file_path, filename=file_code + os.path.splitext(file.original_filename)[1])
    
@app.delete("/delete-file/{file_code}")
def delete_file_route(file_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Retrieve the file record from the database
    file = db.query(File).filter(File.filename == file_code).first()
    
    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Check if the file is owned by the current user
    if file.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    file_path = os.path.join(UPLOAD_FOLDER, file_code + os.path.splitext(file.original_filename)[1])
    logging.info("Attempting to delete file from path: %s", file_path)

    # Check if the file exists on the server
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on the server")

    # Delete the file from the server
    os.remove(file_path)
    logging.info("File deleted from the server.")

    # Delete the file record from the database
    db.delete(file)
    db.commit()

    return {"message": "File deleted successfully"}

@app.on_event("startup")
async def startup_event():
    start_scheduler()

@app.get("/user/files", response_model=List[FileBase])
def get_user_files(current_user: UserBase = Depends(get_current_user), db: Session = Depends(get_db)):
    user_files = db.query(File).filter(File.owner_id == current_user.id).all()
    return user_files

@app.get("/auto-deleted-files", response_model=List[FileBase])
def get_auto_deleted_files(db: Session = Depends(get_db)):
    auto_deleted_files = db.query(File).filter(File.expiry_date <= datetime.utcnow()).all()
    return auto_deleted_files
