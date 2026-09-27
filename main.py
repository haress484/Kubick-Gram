import os
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from supabase import create_client, Client
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not all([SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY]):
    raise ValueError("Missing required environment variables")

supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_service: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI(title="Messenger API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=30)

class SendMessageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)

class MessageResponse(BaseModel):
    id: str
    user_id: str
    username: str
    text: str
    created_at: str

class UserResponse(BaseModel):
    id: str
    username: str

def get_current_user(request: Request) -> dict:
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        user = supabase_anon.auth.get_user(access_token)
        return user.user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=3600
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=604800
    )

def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

@app.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest, response: Response):
    try:
        auth_response = supabase_anon.auth.sign_up({
            "email": f"{request.username.lower()}_{datetime.now().timestamp()}@messenger.local",
            "password": os.urandom(16).hex(),
            "options": {
                "data": {
                    "username": request.username
                }
            }
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Failed to create user")
        
        set_auth_cookies(
            response,
            auth_response.session.access_token,
            auth_response.session.refresh_token
        )
        
        return UserResponse(
            id=auth_response.user.id,
            username=request.username
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    username = user.user_metadata.get("username", "Unknown")
    
    return UserResponse(
        id=user.id,
        username=username
    )

@app.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}

@app.post("/send", response_model=MessageResponse)
async def send_message(
    request: SendMessageRequest,
    response: Response,
    user: dict = Depends(get_current_user)
):
    try:
        username = user.user_metadata.get("username", "Unknown")
        
        result = supabase_service.table("messages").insert({
            "user_id": user.id,
            "text": request.text
        }).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to save message")
        
        message = result.data[0]
        
        return MessageResponse(
            id=message["id"],
            user_id=message["user_id"],
            username=username,
            text=message["text"],
            created_at=message["created_at"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")

@app.get("/messages")
async def get_messages(
    since_id: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(get_current_user)
):
    try:
        query = supabase_service.table("messages").select(
            "id, user_id, text, created_at"
        ).order("created_at", desc=False).limit(limit)
        
        if since_id:
            last_message = supabase_service.table("messages").select("created_at").eq("id", since_id).single().execute()
            
            if last_message.data:
                query = query.gt("created_at", last_message.data["created_at"])
        
        result = query.execute()
        
        messages = []
        for msg in result.data:
            messages.append({
                "id": msg["id"],
                "user_id": msg["user_id"],
                "username": "Unknown",
                "text": msg["text"],
                "created_at": msg["created_at"]
            })
        
        return messages
    
    except Exception as e:
        print(f"Get messages error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load messages")

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
