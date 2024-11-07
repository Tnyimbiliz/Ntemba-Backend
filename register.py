from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from database import register_collection  # Assuming you have a collection named register_collection
import shortuuid  # Import shortuuid for ID generation
from user import get_current_active_user, UserInDB  # Importing from your existing user.py

# Pydantic model for Register
class Register(BaseModel):
    id: Optional[str] = Field(default_factory=shortuuid.uuid, alias="id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    store_name: str
    store_owner_first_name: str
    store_owner_last_name: str
    store_owner_number: str
    store_owner_email: EmailStr
    category: str
    store_instagram: Optional[str] = None
    store_facebook: Optional[str] = None
    store_location: Optional[str] = None
    description: str

# Pydantic model for creating a Register
class RegisterCreate(BaseModel):
    store_name: str
    store_owner_first_name: str
    store_owner_last_name: str
    store_owner_number: str = Field(..., pattern=r'^\+260[0-9]{9}$')  # Ensure the number starts with +260 and is followed by 9 digits
    store_owner_email: EmailStr
    category: str
    store_instagram: Optional[str] = None
    store_facebook: Optional[str] = None
    store_location: Optional[str] = None
    description: str

router = APIRouter(
    prefix="/register",
    tags=["register"]
)

# Endpoint to create a new register entry
@router.post("/", response_model=Register)
async def create_register_entry(register: RegisterCreate):
    register_dict = register.dict()
    register_dict['id'] = shortuuid.uuid()  # Generate a short UUID for the Register ID
    register_dict['timestamp'] = datetime.utcnow()  # Set the current timestamp
    
    register_collection.insert_one(register_dict)
    return Register(**register_dict)

# Endpoint to get a register entry by ID
@router.get("/{register_id}", response_model=Register)
async def get_register_entry(register_id: str):
    register = register_collection.find_one({"id": register_id})
    if register:
        return Register(**register)
    raise HTTPException(status_code=404, detail="Register entry not found")

# Endpoint to list all register entries
@router.get("/", response_model=list[Register])
async def list_register_entries():
    register_entries = register_collection.find({})
    return [Register(**entry) for entry in register_entries]

# Endpoint to update a register entry by ID
@router.put("/{register_id}", response_model=Register)
async def update_register_entry(register_id: str, register: RegisterCreate, current_user: UserInDB = Depends(get_current_active_user)):
    if current_user.type != 1:
        raise HTTPException(status_code=401, detail="Not authorized")
    register_dict = register.dict()
    result = register_collection.update_one({"id": register_id}, {"$set": register_dict})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Register entry not found or no changes made")
    
    updated_entry = register_collection.find_one({"id": register_id})
    return Register(**updated_entry)

# Endpoint to delete a register entry by ID
@router.delete("/{register_id}", response_model=Register)
async def delete_register_entry(register_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    if current_user.type != 1:
        raise HTTPException(status_code=401, detail="Not authorized")
    register = register_collection.find_one_and_delete({"id": register_id})
    if register:
        return Register(**register)
    raise HTTPException(status_code=404, detail="Register entry not found")
