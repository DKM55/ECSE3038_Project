from datetime import datetime,timedelta
from typing import Annotated, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, BeforeValidator, TypeAdapter, Field
import motor.motor_asyncio
from dotenv import dotenv_values
from bson import ObjectId
from pymongo import ReturnDocument
from fastapi.middleware.cors import CORSMiddleware
import requests 
import re
config = dotenv_values(".env")

client = motor.motor_asyncio.AsyncIOMotorClient(config["MONGO_URL"])
db = client.tank_man

app = FastAPI()

origins=[
    "http://localhost:8000",
    "https://simple-smart-hub-client.netlify.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PyObjectId = Annotated[str, BeforeValidator(str)]


regex = re.compile(r'((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')

def parse_time(time_str):
    parts = regex.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)


@app.options("/graph")
async def options_parameter(request: Request):
    # You can include additional checks here if needed
    return Response(status_code=200, headers={
        "Access-Control-Allow-Origin":origins,  # or specify domains
        "Access-Control-Allow-Methods": "PUT",
        "Access-Control-Allow-Headers": "*",  # or specify headers
        "Access-Control-Allow-Credentials":True
    })
@app.options("/settings")
async def options_parameter(request: Request):
    # You can include additional checks here if needed
    return Response(status_code=200, headers={
        "Access-Control-Allow-Origin": origins,  # or specify domains
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Headers": "*",  # or specify headers
        "Access-Control-Allow-Credentials":True
    })
@app.get("/graph")
async def get_parameter(request: Request, size: int = 10):
    sensor_input = await db["data_input"].find().sort("datetime", -1).to_list(size)

    output: List[Dict[str]] = []

    for data in sensor_input:
        temperature = data.get("temperature", 0.0)
        presence = data.get("presence", False)
        datetime_str = data.get("datetime", datetime.now().isoformat())

        output.append({
            "temperature": temperature,
            "presence": presence,
            "datetime": datetime_str
        })

    # If the size of the output is less than requested, pad with default values
    while len(output) < size:
        output.append({
            "temperature": 0.0,
            "presence": False,
            "datetime": datetime.now().isoformat()
        })

    # Sort the output in ascending order of time
    output = sorted(output, key=lambda x: x["datetime"])

    return output

    


class Outside(BaseModel):
    id: Optional[PyObjectId] = Field(alias = "_id", default = None)
    user_temp: Optional[float] = None
    user_light: Optional[str] = None
    light_time_off: Optional[float] = None


   
class UserPreference(BaseModel):
    user_temp: float
    user_light: str
    light_time_off: str 

class UserPreferenceResponse(BaseModel):
    user_pref: UserPreference

@app.put("/settings", response_model=UserPreferenceResponse, status_code=200)
async def create_or_update_parameter(request: Request):
    parameter = await request.json()

    temp = parameter["user_temp"]
    light = parameter["user_light"]
    duration_time = parameter["light_duration"]

    if parameter["user_light"] == "sunset":
        light_select = dark_time()
    else:
        light_select = datetime.strptime(light, "%H:%M:%S").time()

    duration_timedelta = parse_time(duration_time)
    end_time = datetime.combine(datetime.today(), light_select) + duration_timedelta
    duration_time = end_time.time()
    user_data = {
        "user_temp": temp,
        "user_light": str(light_select),
        "light_time_off": str(duration_time)
    }

    # Check if there's an existing user preference
    existing_user_pref = await db["user_pref"].find_one({})
    if existing_user_pref:
        # Update existing user preference
        await db["user_pref"].update_one({}, {"$set": user_data})
        input_select = await db["user_pref"].find_one({})
    else:
        # Insert new user preference
        user_select = await db["user_pref"].insert_one(user_data)
        input_select = await db["user_pref"].find_one({"_id": user_select.inserted_id})

    return UserPreferenceResponse(user_pref=UserPreference(**input_select))

@app.options("/settings")
async def options_settings(request: Request):
    response = Response()
    response.headers["Access-Control-Allow-Methods"] = "PUT"
    response.headers["Access-Control-Allow-Origin"] = origins
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


    

def dark_time():
    response= requests.get("https://api.sunrise-sunset.org/json?lat=18.1155&lng=-77.2760")
    data= response.json()
    sunset= data["results"]["sunset"]
    utc_sunset=datetime.strptime(sunset, "%I:%M:%S %p")
    time_string='06:00:00'
    time_object= datetime.strptime(time_string, '%H:%M:%S').time()
    est_sunset_time= datetime.combine(datetime.min, utc_sunset.time()) + timedelta(hours=time_object.hour, minutes=time_object.minute, seconds=time_object.second)
    est_sunset_time=(est_sunset_time).time()
    return est_sunset_time






class State(BaseModel):
    temperature: float
    presence: bool
    datetime: str 
    fan: bool
    light: bool
    id: str = Field(alias="_id")  # Alias for the ObjectId fi
class StateResponse(BaseModel):
    state: Optional[State]

id: str = Field(alias="_id")  # Alias for the ObjectId fi



class StateE(BaseModel): #for embedded work
    _id:str
    temperature: float
    presence: bool
    datetime: str
    fan: bool
    light: bool
   
class StateResponse(BaseModel):
    stateE: Optional[StateE]



@app.post("/sensordata", status_code=201)
async def update_state(request: Request):
    update_obj = await request.json()

    sensor_temp = update_obj.get("temperature")
    detection = update_obj.get("presence")
    date_time = datetime.now().isoformat()
   
    update_obj["datetime"] = datetime.now().isoformat()

    user_data = await db["user_pref"].find_one()
    user_temp = user_data.get("user_temp")
    user_light = user_data.get("user_light")
    duration_time = user_data.get("light_time_off")
    

    if len(update_obj)==0:
        return{"NO DATA SENT"}

    if len(user_data)==0 or not update_obj or not detection:
        return {
            "fan": False,
            "light": False,
            "current_time": datetime.now()
        }

    if isinstance(sensor_temp, int) and isinstance(user_temp, int):
        update_obj["fan"] = sensor_temp >= user_temp and detection
    else:
        update_obj["fan"] = False

    if user_light and date_time :
        update_obj["light"] = user_light <= date_time < duration_time 
    else:
        update_obj["light"] = False

    updated_data = await db["data_input"].insert_one(update_obj)
    send_data = await db["data_input"].find_one({"_id": updated_data.inserted_id})
    update_obj_without_id = {key: value for key, value in update_obj.items() if key != "_id"}
    updated_data = await db["last_updated"].replace_one({}, update_obj_without_id, upsert=True)

    
    return {
        "STATUS UPDATED" 
    }


@app.get("/sensordata", status_code=200)
async def get_states() -> StateE:
    stateE_object = await db["last_updated"].find().sort('datetime', -1).limit(1).to_list(1)
    if not stateE_object:
        return StateE(
            temperature=0.0,
            presence=False,
            datetime=datetime.now(),
            fan=False,
            light=False,
            
        )
    
    

    return stateE_object[0]



