from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from database import store_collection, store_rating_collection  # Assuming you have these collections
from user import get_current_active_user, UserInDB  # Importing from your existing user.py

# Pydantic model for storeRating
class storeRating(BaseModel):
    store_id: str
    user_id: str
    rating: float  # Rating value between 1 and 5

class StoreRatinginDB(BaseModel):
    store_id: str
    rating: float
    
router = APIRouter(
    prefix="/store/rating",
    tags=["store_rating"]
)

# Endpoint to get the rating of a store
@router.get("/rating/{store_id}")
async def get_store_rating(store_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    store = store_collection.find_one({"id": store_id})
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="store not found")
    
    rating = store_rating_collection.find_one({"user_id": current_user.id})
    
    if not rating:
        return {
            "rating":store["rating"],
            "rating_count": store["rating_count"]
        }

    else:
        return {
            "rating":store["rating"],
            "my_rating": rating["rating"],
            "rating_count": store["rating_count"]
        }
      

# Endpoint to rate a store
@router.post("/")
async def rate_store(store_rating: StoreRatinginDB, current_user: UserInDB = Depends(get_current_active_user)):
    # Validate rating value (should be between 1 and 5)
    if store_rating.rating < 1 or store_rating.rating > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1 and 5."
        )

    # Check if the store exists
    store = store_collection.find_one({"id": store_rating.store_id})
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="store not found")

    # Check if the user has already rated this store
    existing_rating = store_rating_collection.find_one({"store_id": store_rating.store_id, "user_id": current_user.id})
    
    if existing_rating:
        # Update the user's rating
        store_rating_collection.update_one(
            {"store_id": store_rating.store_id, "user_id": current_user.id},
            {"$set": {"rating": store_rating.rating}}  # Update the user's rating
        )

    else: 
        # If user hasn't rated, add the new rating
        store_rating_collection.insert_one({
            "store_id": store_rating.store_id,
            "user_id": current_user.id,
            "rating": store_rating.rating
        })

    # After adding the rating, recalculate the average rating
    return await update_store_rating(store_rating.store_id)

# Helper function to update the average rating of an store
async def update_store_rating(store_id: str):
    store = store_collection.find_one({"id": store_id})
    
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="store not found")
    
    # Get all ratings for the store
    ratings = store_rating_collection.find({"store_id": store_id})
    ratings_list = list(ratings)

    if not ratings_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No ratings available for this store.")
    
    # Calculate the new average rating
    total_rating = sum(rating['rating'] for rating in ratings_list)
    new_average_rating = total_rating / len(ratings_list)
    
    # Update the store's rating and rating count
    store_collection.update_one(
        {"id": store_id},
        {
            "$set": {
                "rating": new_average_rating
            },
            "$set": {
                "rating_count": len(ratings_list)
            }
        }
        
    )
    store_collection.update_one({"id": store_id}, {"$set": {"rating": new_average_rating}})
    
    return {
        "rating": new_average_rating,
        "rating_count": len(ratings_list)
    }
