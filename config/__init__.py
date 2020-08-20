import json

class Config:
    def __init__(self,config_file_name="config.json"):
        with open(config_file_name,"r") as config:
            f=dict(json.load(config))
            for key,value in f.items():
                setattr(self,key,value)