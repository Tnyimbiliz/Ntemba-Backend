from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File, Form
import os
from typing import List, Optional
from pydantic import BaseModel, Field
import shortuuid
from database import items_collection, store_collection
from user import get_current_active_user, UserInDB

# Pydantic model for Item
class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    store_id: str
    categories: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None  # URL or path to the uploaded image

class ItemInDB(Item):
    id: str = Field(default_factory=shortuuid.uuid)

router = APIRouter(
    prefix='/item',
    tags=['item']
)

# Create an item with an image (authentication required)
@router.post("/create_item/", response_model=ItemInDB)
async def create_item(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    categories: List[str] = Form(...),
    image: UploadFile = File(None),  # Optional image file upload
    current_user: UserInDB = Depends(get_current_active_user)
):
    # Check if the user has a store
    store = store_collection.find_one({"user_id": current_user.id, "verified": 1})
    if not store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a store. Please create a store before adding items."
        )

    # Process the image file if provided
    image_url = None
    if image:
        # Ensure the directory exists
        image_dir = "C://Users//LENOVO//Desktop//flutter//Ntemba//BackEnd//Django//MongoTest//ntemba//public//images"
        os.makedirs(image_dir, exist_ok=True)

        image_path = os.path.join(image_dir, image.filename)
        with open(image_path, "wb") as f:
            f.write(await image.read())
        image_url = f"images/{image.filename}"

    # Prepare item data
    item_data = {
        "id": shortuuid.uuid(),
        "name": name,
        "description": description,
        "price": price,
        "store_id": store['id'],
        "categories": categories,
        "image_url": image_url
    }

    # Insert item into database
    items_collection.insert_one(item_data)
    return ItemInDB(**item_data)

# Get a specific item by ID (authentication required)
@router.get("/get_item_by_id/{item_id}", response_model=ItemInDB)
async def get_item(item_id: str):
    item = items_collection.find_one({"id": item_id})
    if item:
        return ItemInDB(**item)
    raise HTTPException(status_code=404, detail="Item not found or not authorized")

# Get all items
@router.get("/get_items/", response_model=List[ItemInDB])
async def get_items():
    items = []
    for item in items_collection.find():
        items.append(ItemInDB(**item))
    return items

# Get all items by the current user
@router.get("/get_items_by_me/", response_model=List[ItemInDB])
async def get_items_by_me(current_user: UserInDB = Depends(get_current_active_user)):
    items = []
    for store in store_collection.find({"user_id": current_user.id}):
        for item in items_collection.find({"store_id": store["id"]}):
            items.append(ItemInDB(**item))
    return items

# Get all items by a particular store
@router.get("/get_items_by/{store_id}", response_model=List[ItemInDB])
async def get_items_by_store(store_id: str):
    items = []
    for item in items_collection.find({"store_id": store_id}):
        items.append(ItemInDB(**item))
    return items

# Update an item by ID (authentication required)
@router.put("/update_item/{item_id}", response_model=ItemInDB)
async def update_item(item_id: str, item: Item, current_user: UserInDB = Depends(get_current_active_user)):
    result = items_collection.update_one(
        {"id": item_id, "user_id": current_user.id},
        {"$set": item.dict()}
    )
    if result.modified_count:
        updated_item = items_collection.find_one({"id": item_id})
        return ItemInDB(**updated_item)
    raise HTTPException(status_code=404, detail="Item not found or not authorized")

# Delete an item by ID (authentication required)
@router.delete("/delete_item/{item_id}")
async def delete_item(item_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    store = store_collection.find_one({"user_id": current_user.id})
    result = items_collection.delete_one({"id": item_id, "store_id": store["id"]})
    if result.deleted_count:
        return {"message": "Item deleted"}
    raise HTTPException(status_code=404, detail="Item not found or not authorized")

# Search for items by keyword
@router.get("/search_items/", response_model=List[ItemInDB])
async def search_items(
    query: str = Query(..., min_length=3, description="Search query string"),
    limit: int = Query(10, description="Limit the number of search results")
):
    search_criteria = {
        "$or": [
            {"name": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}}
        ]
    }
    items = []
    cursor = items_collection.find(search_criteria).limit(limit)
    for item in cursor:
        items.append(ItemInDB(**item))
    return items

# Search for items by category (partial match)
@router.get("/search_items_by_category/", response_model=List[ItemInDB])
async def search_items_by_category(
    category: str = Query(..., description="Category to search for"),
    limit: int = Query(10, description="Limit the number of search results")
):
    # Use regex to allow partial matching of the category
    search_criteria = {
        "categories": {"$regex": category, "$options": "i"}  # Case-insensitive match
    }

    items = []
    cursor = items_collection.find(search_criteria).limit(limit)
    for item in cursor:
        items.append(ItemInDB(**item))
    return items

