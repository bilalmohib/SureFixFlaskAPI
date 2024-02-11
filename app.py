# app.py

# Required imports
import os
import uuid
from flask import Flask, request, jsonify, Blueprint,current_app
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime, timedelta
import pyrebase
from firebaseConfig import config
from flasgger import Swagger
from jsonschema import validate, ValidationError
import time

# Initialize Flask app
app = Flask(__name__)
swagger = Swagger(app)

# Initialize Firestore DB Firestore isnt present in pyrebase so thats why had to use firebase_admin for that
cred = credentials.Certificate('key.json')
default_app = initialize_app(cred)

# This one is required for managing auth and disbaled users properly
firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firestore.client()
user_Ref = db.collection('user')
todo_ref = db.collection('todos')

TODO_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "createdAt": {"type": "string"},
        "updatedAt": {"type": "string"},
        "createdBy": {"type": "string"},
        "isCompleted": {"type": "boolean"},
        "activated": {"type": "boolean"}
    },
    "required": ["title"]
}

# Sign up schema
SIGNUP_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {"type": "string", "format": "email"},
        "password": {"type": "string", "minLength": 6},
        "displayName": {"type": "string", "minLength": 1},
        "photoURL": {"type": "string"}
    },
    "required": ["email", "password", "displayName"]
}

# Custom function to enable user after successful login
def enable_user(email):
    try:
        user = auth.get_user_by_email(email)
        if user.disabled:
            auth.update_user(user.uid, disabled=False)
        return True
    except Exception as e:
        return str(e)

# Authentication middleware
def authenticate_user(token):
    try:
        user = auth.get_account_info(token)["users"][0]
        
        if not user:
            return False, "Invalid token"
        user = user

        print("User Info: ", user["email"], user["emailVerified"], user["disabled"])

        # if not user["emailVerified"]:
        #     return False, "Email not verified"
        if not user["disabled"]:
            return True, user
        return False, "User is disabled"
    except Exception as e:
        return False, str(e)

@app.route('/signup', methods=['POST'])
def signup():
    """
    Register a new user.
    ---
    parameters:
      - name: email
        in: formData
        type: string
        required: true
        description: Email address of the user
      - name: password
        in: formData
        type: string
        required: true
        description: Password of the user
      - name: displayName
        in: formData
        type: string
        required: true
        description: Display Name of the user
      - name: photoURL
        in: formData
        type: string
        required: false
        description: Photo URL of the user
    responses:
      201:
        description: User created successfully
      400:
        description: Error message
    """
    email = request.json.get('email')
    password = request.json.get('password')
    displayName = request.json.get('displayName')
    photoURL = request.json.get('photoURL')

    try:
        if not displayName:
            return jsonify({
                'message': 'Display Name is required',
                "RequiredPropertiesForSignUp": SIGNUP_SCHEMA.get('required')
                }), 400
        
        user = auth.create_user_with_email_and_password(email=email, password=password)

        # Enable user after successful login
        isUserEnabled = enable_user(email)

        if isUserEnabled:
            user_data = {
                "displayName": displayName,
                "email": email,
                "photoURL": photoURL,
            }           

            # set the display name and photo URL
            auth.update_profile(
                user['idToken'], 
                user_data.get('displayName'),
                user_data.get('photoURL')
              )

            return jsonify({
                'message': 'User created successfully',
                'user': user,
                'localId': user['localId'],
            }), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    """
    Authenticate user by email and password.
    ---
    tags:
      - Authentication
    parameters:
      - name: email
        in: formData
        type: string
        required: true
        description: Email address of the user
      - name: password
        in: formData
        type: string
        required: true
        description: Password of the user
    responses:
      200:
        description: User authenticated successfully
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: Access token for the authenticated user
      401:
        description: Authentication failed
        schema:
          type: object
          properties:
            error:
              type: string
              description: Error message
    """
    try:
        email = request.json.get('email')
        password = request.json.get('password')

        user = auth.sign_in_with_email_and_password(email, password)

        # Enable user after successful login
        # isUserEnabled = enable_user(email)

        # if isUserEnabled:
        #     return jsonify({"access_token": user}), 200
        # else:
        #     return jsonify(
        #         {
        #         "error": "User is disabled: ",
        #         "errorDetails": isUserEnabled,
        #         "message": "Please contact the administrator to enable your account"
        #         }), 401

        return jsonify({"access_token": user}), 200

    except Exception as e:
        return jsonify({"error": f"An Error Occurred: {e}"}), 401

@app.route('/todo', methods=['GET'])
def get_todos():
    """
    Retrieve todos for the authenticated user.
    ---
    tags:
      - Todos
    security:
      - BearerAuth: []
    responses:
      200:
        description: Todos retrieved successfully
        schema:
          type: object
          properties:
            todos:
              type: array
              items:
                $ref: '#/definitions/TODO_SCHEMA'
      401:
        description: Unauthorized access
        schema:
          type: object
          properties:
            message:
              type: string
              description: Error message
    """
    token = request.headers.get('Authorization')

    # Split the token string by space and take the second part
    barrier_token = token.split(" ")[1]

    authenticated, user = authenticate_user(barrier_token)

    if authenticated:
        todos_ref = db.collection('todos').stream()
        todos = [{**todo.to_dict(), "id": todo.id} for todo in todos_ref]
        return jsonify({'todos': todos}), 200
    return jsonify({'message': 'Unauthorized','errorDetails':user}), 401

@app.route('/todo', methods=['POST'])
def add_todo():
    """
    Add a new todo for the authenticated user.
    ---
    tags:
      - Todos
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          $ref: '#/definitions/TODO_SCHEMA'  # Reference to the schema definition
    responses:
      200:
        description: Todo added successfully
        schema:
          type: object
          properties:
            message:
              type: string
              description: Success message
      400:
        description: Invalid request body
        schema:
          type: object
          properties:
            message:
              type: string
              description: Error message
      401:
        description: Unauthorized access
        schema:
          type: object
          properties:
            message:
              type: string
              description: Error message
    definitions:  # Define the schema here
      TODO_SCHEMA:
        type: object
        properties:
          title:
            type: string
            description: Title of the todo
          description:
            type: string
            description: Description of the todo
          isCompleted:
            type: boolean
            description: Flag indicating whether the todo is completed
          activated:
            type: boolean
            description: Flag indicating whether the todo is activated
        required:
          - title  # title is a required field
    """
    token = request.headers.get('Authorization')

    # Split the token string by space and take the second part
    barrier_token = token.split(" ")[1]

    authenticated, user = authenticate_user(barrier_token)
    if authenticated:
        data = request.json

        # Set default values and format fields as required
        title = data.get('title')
        description = data.get('description', "")
        createdAt = time.strftime("%Y-%m-%d %H:%M:%S")
        updatedAt = createdAt
        createdBy = user["email"]
        isCompleted = data.get('isCompleted', False)
        activated = data.get('activated', False)

        todo_data = {
            "title": title,
            "description": description,
            "createdAt": createdAt,
            "updatedAt": updatedAt,
            "createdBy": createdBy,
            "isCompleted": isCompleted,
            "activated": activated
        }

        try:
            # Validate the request body against the fixed schema
            validate(instance=todo_data, schema=TODO_SCHEMA)
        except ValidationError as e:
            # If validation fails, return a 400 Bad Request response
            return {
                "message": 'Invalid request body',
                "errors":e.message,
                "RequiredSchema": TODO_SCHEMA
            }, 400

        todo_ref = db.collection('todos').document()
        todo_ref.set(todo_data)
        return jsonify({'message': 'Todo added successfully'}), 200
    return jsonify({'message': "Unauthorized: ",'errorDetails':user}), 401

@app.route('/todo/<todo_id>', methods=['GET'])
def get_todo(todo_id):
    """
    Retrieve a todo by its ID.
    ---
    tags:
      - Todos
    security:
      - BearerAuth: []
    parameters:
      - name: todo_id
        in: path
        type: string
        required: true
        description: ID of the todo to retrieve
    responses:
      200:
        description: Todo retrieved successfully
        schema:
          type: object
          properties:
            id:
              type: string
              description: Unique identifier for the todo
            title:
              type: string
              description: Title of the todo
            description:
              type: string
              description: Description of the todo
            created_at:
              type: string
              format: date-time
              description: Date and time when the todo was created
      401:
        description: Unauthorized access
        schema:
          type: object
          properties:
            message:
              type: string
              description: Error message
      404:
        description: Todo not found
        schema:
          type: object
          properties:
            message:
              type: string
              description: Error message
    """
    token = request.headers.get('Authorization')

    # Split the token string by space and take the second part
    barrier_token = token.split(" ")[1]

    authenticated, user = authenticate_user(barrier_token)
    if authenticated:
        todo_ref = db.collection('todos').document(todo_id).get()
        if todo_ref.exists:
            return jsonify(todo_ref.to_dict()), 200
        return jsonify({'message': 'Todo not found'}), 404
    return jsonify({'message': 'Unauthorized','errorDetails':user}), 401

@app.route('/todo/<todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """
    Delete a todo by its ID.
    ---
    tags:
      - Todos
    security:
      - BearerAuth: []
    parameters:
      - name: todo_id
        in: path
        type: string
        required: true
        description: ID of the todo to delete
    responses:
      200:
        description: Todo deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              description: Success message
      401:
        description: Unauthorized access
        schema:
          type: object
          properties:
            message:
              type: string
              description: Error message
    """
    token = request.headers.get('Authorization')

    # Split the token string by space and take the second part
    barrier_token = token.split(" ")[1]

    authenticated, user = authenticate_user(barrier_token)
    if authenticated:
        db.collection('todos').document(todo_id).delete()
        return jsonify({'message': 'Todo deleted successfully'}), 200
    return jsonify({'message': 'Unauthorized','errorDetails':user}), 401

port = int(os.environ.get('PORT', 8080))
if __name__ == '__main__':
    app.run(threaded=True, host='0.0.0.0', port=port)
