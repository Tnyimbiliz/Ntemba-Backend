from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from database import store_collection  # Assuming you have a collection named store_collection
import shortuuid  # Import shortuuid for ID generation
from user import get_current_active_user, UserInDB  # Importing from your existing user.py

# Pydantic model for Store
class Store(BaseModel):
    id: Optional[str] = Field(default_factory=shortuuid.uuid, alias="id")
    user_id: str
    name: str
    verified: int = 0  # Default is not verified
    followers: int = 0  # Default is 0 followers
    rating: float = 0.0  # Default is 0 rating (out of 5 stars)
    rating_count: int = 0

class StoreInDB(Store):
    id: str = Field(default_factory=shortuuid.uuid)
    user_id: str

# Pydantic model for creating a Store
class StoreCreate(BaseModel):
    name: str

# Pydantic model for StoreRating
class StoreRating(BaseModel):
    rating: float  # Rating value between 1 and 5

router = APIRouter(
    prefix="/store",
    tags=["store"]
)

# Endpoint to create a new store
@router.post("/", response_model=Store)
async def create_store(store: StoreCreate, current_user: UserInDB = Depends(get_current_active_user)):
    # Check if a store with the same name already exists
    existing_store = store_collection.find_one({"name": store.name})
    if existing_store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A store with this name already exists."
        )
    
    store_dict = store.dict()
    store_dict['id'] = shortuuid.uuid()  # Generate a short UUID for the Store ID
    store_dict['user_id'] = current_user.id  # Set the user_id to the current user's ID
    store_dict['verified'] = 1  # Default not verified //changed for demo
    store_dict['followers'] = 0  # Default 0 followers
    store_dict['rating'] = 0.0  # Default 0 rating
    store_dict['rating_count'] = 0.0  # Default 0 rating
    
    store_collection.insert_one(store_dict)
    return Store(**store_dict)

# Endpoint to get a store by ID
@router.get("/{store_id}", response_model=Store)
async def get_store(store_id: str):
    store = store_collection.find_one({"id": store_id})
    if store:
        return Store(**store)
    raise HTTPException(status_code=404, detail="Store not found")

# Endpoint to list all stores
@router.get("/", response_model=List[Store])
async def list_stores(current_user: UserInDB = Depends(get_current_active_user)):
    if current_user.type == 1:  # If the user is an admin
        stores = store_collection.find({})
    else:  # Only show verified stores to non-admin users
        stores = store_collection.find({"verified": 1})
    
    return [Store(**store) for store in stores]

# Endpoint to list all stores
@router.put("/verify/{store_id}", response_model=Store)
async def verify_store(store_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    # Check if the current user is an admin
    if current_user.type != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to verify stores."
        )
    
    # Find the store by ID
    store = store_collection.find_one({"id": store_id})
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found."
        )
    
    # Update the store's verified status to 1 (verified)
    store_collection.update_one({"id": store_id}, {"$set": {"verified": 1}})
    
    # Return the updated store
    updated_store = store_collection.find_one({"id": store_id})
    return Store(**updated_store)

# Search for stores (modern search logic, only show verified stores)
@router.get("/search_stores/", response_model=List[StoreInDB])
async def search_stores(
    query: str = Query(..., min_length=3, description="Search query string"),
    limit: int = Query(10, description="Limit the number of search results")
):
    search_criteria = {
        "$and": [
            {"verified": 1},  # Ensure the store is verified
            {"name": {"$regex": query, "$options": "i"}}
        ]
    }
    stores = []
    cursor = store_collection.find(search_criteria).limit(limit)
    for store in cursor:
        stores.append(StoreInDB(**store))
    return stores

# Endpoint to get a store by ID
@router.get("/get_storename/{store_id}")
async def get_store(store_id: str):
    store = store_collection.find_one({"id": store_id})
    if store:
        return store["name"]
    raise HTTPException(status_code=404, detail="Store not found")

# Endpoint to get whether the user is an admin or not
@router.get("/get_storeid/")
async def get_store_id(current_user: UserInDB = Depends(get_current_active_user)):
    store = store_collection.find_one({"user_id": current_user.id})
    if store:
        return store["id"]
    raise HTTPException(status_code=404, detail="Store not found")
    
# Endpoint to get whether the user is an admin or not
@router.get("/storename/")
async def get_this_store_name(current_user: UserInDB = Depends(get_current_active_user)):
    store = store_collection.find_one({"user_id": current_user.id})
    if store:
        return store["name"]
    raise HTTPException(status_code=404, detail="Store not found")
    
# Endpoint to get whether the user is an admin or not
@router.get("/has_store/")
async def get_store_status(current_user: UserInDB = Depends(get_current_active_user)):
    store = store_collection.find_one({"user_id": current_user.id})
    if not store:
        if current_user.type == 2:
            return 2
        else:
            return 0
    try:
        if store:
            return 1
        elif (current_user.type == 2):
            return 2
        else:
            return 0
    except:
        return 0
    
# Search for stores (modern search logic)
@router.get("/search_stores/", response_model=List[StoreInDB])
async def search_stores(
    query: str = Query(..., min_length=3, description="Search query string"),
    limit: int = Query(10, description="Limit the number of search results")
):
    search_criteria = {
        "$or": [
            {"name": {"$regex": query, "$options": "i"}},
            {"followers": {"$regex": query, "$options": "i"}}
        ],
        "verified": 1  # Only return verified stores
    }
    
    stores = []
    cursor = store_collection.find(search_criteria).limit(limit)
    for store in cursor:
        stores.append(StoreInDB(**store))
    return stores

# Endpoint to rate a store
@router.post("/rate/{store_id}")
async def rate_store(store_id: str, store_rating: StoreRating, current_user: UserInDB = Depends(get_current_active_user)):
    # Validate rating value (should be between 1 and 5)
    if store_rating.rating < 1 or store_rating.rating > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1 and 5."
        )

    # Check if the store exists
    store = store_collection.find_one({"id": store_id})
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    # Get the current rating and rating count from the store
    current_rating = store.get("rating", 0.0)
    rating_count = store.get("rating_count", 0)

    # Calculate new average rating
    new_rating_count = rating_count + 1
    new_average_rating = ((current_rating * rating_count) + store_rating.rating) / new_rating_count

    # Update the store's rating and rating count
    store_collection.update_one(
        {"id": store_id},
        {
            "$set": {
                "rating": new_average_rating,
                "rating_count": new_rating_count
            }
        }
    )

    return {
        "message": "Store rated successfully",
        "new_rating": new_average_rating,
        "total_ratings": new_rating_count
    }