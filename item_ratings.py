from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from database import items_collection, item_rating_collection  # Assuming you have these collections
from user import get_current_active_user, UserInDB  # Importing from your existing user.py

# Pydantic model for itemRating
class itemRating(BaseModel):
    item_id: str
    user_id: str
    rating: float  # Rating value between 1 and 5

class ItemRatinginDB(BaseModel):
    item_id: str
    rating: float
    
router = APIRouter(
    prefix="/item/rating",
    tags=["item_rating"]
)

# Endpoint to get the rating of an item
@router.get("/rating/{item_id}")
async def get_item_rating(item_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    item = items_collection.find_one({"id": item_id})
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    
    rating = item_rating_collection.find_one({"user_id": current_user.id})
    
    if not rating:
        return {
            "rating":item["rating"],
            "rating_count": item["rating_count"]
        }

    else:
        return {
            "rating":item["rating"],
            "my_rating": rating["rating"],
            "rating_count": item["rating_count"]
        }
      

# Endpoint to rate an item
@router.post("/")
async def rate_item(item_rating: ItemRatinginDB, current_user: UserInDB = Depends(get_current_active_user)):
    # Validate rating value (should be between 1 and 5)
    if item_rating.rating < 1 or item_rating.rating > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1 and 5."
        )

    # Check if the item exists
    item = items_collection.find_one({"id": item_rating.item_id})
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")

    # Check if the user has already rated this item
    existing_rating = item_rating_collection.find_one({"item_id": item_rating.item_id, "user_id": current_user.id})
    
    if existing_rating:
        # Update the user's rating
        item_rating_collection.update_one(
            {"item_id": item_rating.item_id, "user_id": current_user.id},
            {"$set": {"rating": item_rating.rating}}  # Update the user's rating
        )

    else: 
        # If user hasn't rated, add the new rating
        item_rating_collection.insert_one({
            "item_id": item_rating.item_id,
            "user_id": current_user.id,
            "rating": item_rating.rating
        })

    # After adding the rating, recalculate the average rating
    return await update_item_rating(item_rating.item_id)

# Helper function to update the average rating of an item
async def update_item_rating(item_id: str):
    item = items_collection.find_one({"id": item_id})
    
    if not item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="item not found")
    
    # Get all ratings for the item
    ratings = item_rating_collection.find({"item_id": item_id})
    ratings_list = list(ratings)

    if not ratings_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Something went wrong,No ratings available for this item.")
    
    # Calculate the new average rating
    total_rating = sum(rating['rating'] for rating in ratings_list)
    new_average_rating = total_rating / len(ratings_list)
    
    # Update the item's rating and rating count
    items_collection.update_one(
        {"id": item_id},
        {
            "$set": {
                "rating": new_average_rating
            },
            "$set": {
                "rating_count": len(ratings_list)
            }
        }
        
    )
    items_collection.update_one({"id": item_id}, {"$set": {"rating": new_average_rating}})
    
    return {
        "rating": new_average_rating,
        "rating_count": len(ratings_list)
    }
