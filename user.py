from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from database import users_collection
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
import jwt
import shortuuid  # Import shortuuid for ID generation
from typing import Dict, List, Optional

# Pydantic model for User
class User(BaseModel):
    id: Optional[str] = Field(default_factory=shortuuid.uuid, alias="id")
    username: str
    email: str
    full_name: Optional[str] = None
    type: int

class UserInDB(User):
    hashed_password: str

class UserData(User):
    username: str
    id: str

class UserCreate(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    type: int
    password: str

class UserTypeResponse(BaseModel):
    id: str
    username: str
    type: int

router = APIRouter(
    prefix='',
    tags=['user']
)

# JWT and password hashing settings
SECRET_KEY = "44h32345293875249592342wdfs052528435223423b2h342jg3245j234g6n436j3"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Utility functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = users_collection.find_one({"username": username})
    if user is None:
        raise credentials_exception
    return UserInDB(**user)

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    return current_user

# --------- API ENDPOINTS ---------

# User registration
@router.post("/user/", response_model=User)
async def create_user(user: UserCreate):
    user_dict = user.dict()
    user_dict['id'] = shortuuid.uuid()  # Generate a short UUID for the ID
    user_dict['username'] = user_dict['username'].lower()  # Convert username to lowercase
    user_dict['hashed_password'] = get_password_hash(user.password)
    del user_dict['password']
    if users_collection.find_one({"username": user_dict['username']}):
        raise HTTPException(status_code=400, detail="Username already exists")
    users_collection.insert_one(user_dict)
    return User(**user_dict)

# User login and token generation
@router.post("/token", response_model=dict)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    username = form_data.username.lower()  # Convert username to lowercase for login
    user = users_collection.find_one({"username": username})
    if not user or not verify_password(form_data.password, user['hashed_password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user['username']}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

# Endpoint to get whether the user is an admin or not
@router.get("/user/type/")
async def get_user_type(current_user: UserInDB = Depends(get_current_active_user)):
    if current_user.type == 1:
        return "Administrator"
    elif current_user.type == 2:
        return "Delivery"
    else:
        return "Normal"
    
# Endpoint to get whether the user is an admin or not
@router.put("/user/register_rider/")
async def get_user_type(current_user: UserInDB = Depends(get_current_active_user)):
    if current_user.type == 2:
        raise HTTPException(status_code=404, detail="You are already registered as a rider")
    elif current_user.type == 1:
        raise HTTPException(status_code=404, detail="Admin cannot register as a rider")
    else:
        users_collection.update_one({"id": current_user.id}, {"$set": {"type": 2}})
        updated_user = users_collection.find_one({"id": current_user.id})
        return {"message": "Rider Registerd successfully"}

    
# Endpoint to get the current user details
@router.get("/user/details/")
async def get_user_details(current_user: UserInDB = Depends(get_current_active_user)):
    return {"username": current_user.username, "id": current_user.id,"email": current_user.email, "full_name": current_user.full_name, "type": current_user.type}

# Get a specific item by ID (authentication required)
@router.get("/user/data/{user_id}",)
async def get_data(user_id: str):
    user = users_collection.find_one({"id": user_id})
    if user:
        return {"id": user["id"], "username": user["username"], "email": user["email"],"full_name": user["full_name"], "type": user["type"]}
    raise HTTPException(status_code=404, detail="Item not found or not authorized")

# Endpoint to list all usernames and their types
@router.get("/users/", response_model=List[UserTypeResponse])
async def list_usernames_and_types():
    users = users_collection.find({}, {"id":1,"username": 1, "type": 1})
    return [{"id": user["id"], "username": user["username"], "type": user["type"]} for user in users]