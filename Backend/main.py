import os
from fastapi import FastAPI,UploadFile,File,HTTPException,status
from fastapi.responses import FileResponse,JSONResponse

Resume_dir="Resume" 


app=FastAPI()

@app.get('/')
def main_page():
    return {"status":"Backend is healthy"}

@app.get("/home")
def resume_upload():
    return FileResponse("Frontend/index.html")

@app.post("/upload_resume")
async def upload_pdf(pdf_file:UploadFile=File(...)):
    if  pdf_file.content_type!= "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF files are allowed!"
        )

    filepath=os.path.join(Resume_dir,pdf_file.filename)
    try:
        with open(filepath,"wb") as buffer:
            content=await pdf_file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )
    finally:
        await pdf_file.close()
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "status": "success",
            "message": "File successfully uploaded and validated.",
        }
    )