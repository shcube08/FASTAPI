# FASTAPI
fire sharing application
http://51.158.187.113:8000/docs#/

Introduction
Build a simple file sharing web application. The application must allow users to upload and download files with each other.
Specifications
- Users can register and login to the application.
- Users can upload files to the application.
- For each upload a unique code is generated.
- For each upload the user can specify when the file should expire.
- Any other registered user can download the file using the code.
- When another registered tries to download a deleted file, the user should get an error message saying the file has been deleted.
- On expiry the file is deleted from the server.
- The user can also delete the file before the expiry.
- The user should be able to see the list of files uploaded by him along with their expiry.
- The user should be able to see all files that were auto-deleted.
- Do not allow the user to upload a file without logging in.
- Do not allow the user to upload a file without an expiry.
Tools and Tech
- Python as the core coding language
- FastAPI as the web framework
- SQLAlchemy as the ORM
- PostgreSQL as the database
- Pytest as the testing framework
- Deploy the entire app on Digital Ocean.
- Use a logging framework to log all the errors and warnings.
![image](https://github.com/shcube08/FASTAPI/assets/44604254/f006d398-0069-4893-ad10-f6d0c1f49706)

