import boto3
from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File, Form
import os
#from dotenv import load_dotenv
from typing import List, Optional
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import shortuuid
from database import items_collection, store_collection
from user import get_current_active_user, UserInDB

#load_dotenv()

# Retrieve values from the environment
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

router = APIRouter(
    prefix='/item',
    tags=['item']
)

# Initialize S3 client
s3 = boto3.client('s3',
                  aws_access_key_id=AWS_ACCESS_KEY_ID,
                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

# Constants for file validation
MAX_FILE_SIZE_MB = 1
SUPPORTED_FILE_TYPES = {"image/png", "image/jpeg"}


# Pydantic model for Item
class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    store_id: str
    rating: float = 0.0
    rating_count: int = 0.0
    categories: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None  # URL or path to the uploaded image

class ItemInDB(Item):
    id: str = Field(default_factory=shortuuid.uuid)

# Constants for file validation
MAX_FILE_SIZE_MB = 1
SUPPORTED_FILE_TYPES = {"image/png", "image/jpeg"}

# Update the `create_item` endpoint
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
    
    # Generate a unique ID for the item
    id = shortuuid.uuid()

    # Process the image file if provided
    image_url = None
    if image:
        # Validate file type
        if image.content_type not in SUPPORTED_FILE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {image.content_type}. Allowed types are PNG and JPEG."
            )
        # Validate file size
        contents = await image.read()  # Read the file contents to get its size
        file_size_mb = len(contents) / (1024 * 1024)  # Convert size to MB
        if file_size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds 1MB limit."
            )

        # Reset the file cursor after reading for validation
        image.file.seek(0)

        # Upload file to S3 using the item's ID as the filename
        file_extension = image.content_type.split("/")[-1]
        image_filename = f"{id}.{file_extension}"
        print(image_filename)
        s3.upload_fileobj(image.file, AWS_BUCKET_NAME, image_filename)

        # Construct the image URL (assuming the bucket is public)
        image_url = image_filename

    # Prepare item data
    item_data = {
        "id": id,
        "name": name,
        "description": description,
        "price": price,
        "store_id": store['id'],
        "categories": categories,
        "rating": 0.0,
        "rating_count": 0,
        "image_url": image_url
    }

    # Insert item into the database
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

def get_s3_image_url(image_name: str):
    if not image_name:
        raise HTTPException(status_code=400, detail="Image name cannot be empty")

    print(f"Received image name: {image_name}")  # Debug log
    
    try:
        print(f"Attempting to generate URL for image: {image_name}")  # Debug log
        url = s3.generate_presigned_url('get_object',
                                              Params={'Bucket': AWS_BUCKET_NAME, 'Key': image_name},
                                              ExpiresIn=3600)
        print(f"Generated URL: {url}")  # Debug log
        return url
    except Exception as e:
        print(f"Error generating URL: {str(e)}")  # Debug log
        raise HTTPException(status_code=500, detail=f"Error generating image URL: {str(e)}")

@router.get("/image-url/{image_name}")
def image_url(image_name: str):
    if not image_name:
        raise HTTPException(status_code=400, detail="Image name is required.")
    
    return {"image_url": get_s3_image_url(image_name)}