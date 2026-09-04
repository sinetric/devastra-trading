import json

def create_json_file(file_path, data): # create json file and write data to it
    with open(file_path, "w") as json_file:
        json.dump(data.json(), json_file)
    return file_path

def parse_json_file(file_path): # parse json file and return data
    with open(file_path, "r") as json_file:
        data = json.load(json_file)
    return data