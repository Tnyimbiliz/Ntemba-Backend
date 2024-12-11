from pymongo.mongo_client import MongoClient

uri = "mongodb://admin:test12345@ac-fgwem1r-shard-00-00.uxhoyi1.mongodb.net:27017,ac-fgwem1r-shard-00-01.uxhoyi1.mongodb.net:27017,ac-fgwem1r-shard-00-02.uxhoyi1.mongodb.net:27017/?ssl=true&replicaSet=atlas-4y1ezb-shard-0&authSource=admin&retryWrites=true&w=majority&appName=Cluster0"

# Create a new client and connect to the server
client = MongoClient(uri)

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Successfully connected to MongoDB!")
except Exception as e:
    print(e)

# Select the database and collection
database = client.my_database
items_collection = database.items
users_collection = database.users
cart_collection = database.carts
order_collection = database.orders
store_collection = database.stores
register_collection = database.registers
item_rating_collection = database.item_ratings
store_rating_collection = database.store_ratings


