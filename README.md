# Python Flask RESTful API Hosted on Firebase Functions

## Documentation
The API endpoints documentation is given below:
[API DOCS](https://secured-todo-api-rdhs5s76pq-de.a.run.app/apidocs/#)

## Pre-requisites
- Python 3.11 or higher LTS(Latest version)
- G Cloud CLI

## Installation
### Python
- You can install Python by going to this link
[Python Download](https://www.python.org/downloads/)

### G Cloud CLI
- You can install G Cloud CLI by going to this link
[Google Cloud CLI Download](https://cloud.google.com/sdk/docs/install#mac)

## Running the API locally
- Remember to be in the root of the repository to run the following commands
- After installing python, you can install the required packages by running the following command
```sh
pip install -r requirements.txt
```
- After installing the required packages, you can run the following command to start the server
```sh
python app.py
```
- The server will start on the following URL
```sh
http://127.0.0.1:8080
```
- You can test the API by using the following URL
```sh
http://127.0.0.1:8080
```
OR
```sh
http://192.168.1.141:8080
```

## Deploying to Firebase Functions
Steps to deploy the API on your own using firebase functions and G Cloud
<br/>

1- First run
```sh
gcloud init
```
2- Then build the python code to make it ready for deployment
```sh
gcloud builds submit --tag gcr.io/<project-id>/<container-name-any>
``` 
2- Then deploy using the command
```sh
gcloud run deploy --image gcr.io/<project-id>/<container-name-any>
```

## Currrent Container name
<!-- ContainerName="secured-todo-api" -->
ContainerName="surefix"

## Deployment Commands for deploying to Firebase Functions

### Project Build Command
```sh
gcloud builds submit --tag gcr.io/pythonapi-c0178/surefix
```

### Project Build Command
```sh
gcloud run deploy --image gcr.io/pythonapi-c0178/surefix
```