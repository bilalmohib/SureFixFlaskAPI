# app.py

# Required imports
import os
import uuid
from flask import Flask, request, jsonify, Blueprint,current_app
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime, timedelta
import pyrebase
from firebaseConfig import config
from functools import wraps
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
service_ref = db.collection('service')

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

# Service schema
SERVICE_SCHEMA = {
    "type": "object",
    "properties": {
        "sf_id": {"type": "string"},
        "channel": {"type": "string"},
        "contact_details": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "contact_numbers": {
                    "type": "object",
                    "properties": {
                        "primary": {
                            "type": "object",
                            "properties": {
                                "country_code": {"type": "number"},
                                "number": {"type": "number"},
                                "verified": {"type": "boolean"},
                                "whatsapp": {"type": "boolean"}
                            },
                            "required": ["country_code", "number"]
                        },
                        "secondary": {
                            "type": "object",
                            "properties": {
                                "country_code": {"type": "number"},
                                "number": {"type": "number"},
                                "verified": {"type": "boolean"},
                                "whatsapp": {"type": "boolean"}
                            },
                            "required": ["country_code", "number"]
                        }
                    },
                    "required": ["primary", "secondary"]
                },
                "email": {"type": "string"},
                "pickup_address": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string"},
                        "city": {"type": "string"},
                        "state": {"type": "string"},
                        "pincode": {"type": "number"},
                        "google_location": {"type": "string"}
                    },
                    "required": ["address", "city", "state", "pincode"]
                },
                "use_differant_delivery_address": {"type": "boolean"},
                "delivery_address": {
                    "type": "object",
                    "properties": {
                        "address": {"type": "string"},
                        "city": {"type": "string"},
                        "state": {"type": "string"},
                        "pincode": {"type": "number"},
                        "google_location": {"type": "string"}
                    },
                    "required": ["address", "city", "state", "pincode"]
                }
            },
            "required": ["first_name", "last_name", "contact_numbers", "pickup_address", "delivery_address"]
        },
        "machine_details": {
            "type": "object",
            "properties": {
                "item_brand": {"type": "string"},
                "model": {"type": "string"},
                "item_category": {"type": "string"},
                "year_of_purchase": {"type": "number"}
            },
            "required": ["item_brand", "model", "item_category", "year_of_purchase"]
        },
        "issue_message_from_customer": {"type": "string"},
        "admin_comments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string"},
                    "user": {"type": "string"},
                    "message": {"type": "string"}
                },
                "required": ["timestamp", "user", "message"]
            }
        },
        "delivery_note": {"type": "string"},
        "pickup_details": {
            "type": "object",
            "properties": {
                "pickup_note": {"type": "string"}
            },
            "required": ["pickup_note"]
        },
        "self_logistics": {"type": "boolean"}
    },
    "required": ["sf_id", "channel", "contact_details", "machine_details", "issue_message_from_customer", "admin_comments", "delivery_note", "pickup_details", "self_logistics"]
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

        # print("User Info: ", user["email"], user["emailVerified"], user["disabled"])

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
    
# Authentication decorator
def authenticate(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            token = request.headers.get('Authorization')
            
            # Getting the barrier token from the request header
            barrier_token = token.split(" ")[1]
            authenticated, user = authenticate_user(barrier_token)

            # If user is authenticated, call the actual function
            if authenticated:
              return func(user, *args, **kwargs)
            else:
              # If user is not authenticated, return a 401 Unauthorized response
              return jsonify({'message': "Unauthorized: ",'errorDetails':user}), 401
        except Exception as e:
            # If an error occurs, return a 401 Unauthorized response
            return jsonify({'error': 'Unauthorized', 'message': str(e)}), 401
    # Return the actual function to be called
    return wrapper

def save_service_to_database(data, user):
    self_logistics = data.get('self_logistics')
    sf_id = data.get('sf_id')
    channel = data.get('channel')
    contact_details = data.get('contact_details')
    delivery_note = data.get('delivery_note')
    issue_message_from_customer = data.get('issue_message_from_customer')
    machine_details = data.get('machine_details')
    pickup_details = data.get('pickup_details')
    admin_comments = data.get('admin_comments')

    service_body_data = {
        "self_logistics": self_logistics,
        "sf_id": sf_id,
        "channel": channel,
        "contact_details": contact_details,
        "delivery_note": delivery_note,
        "issue_message_from_customer": issue_message_from_customer,
        "machine_details": machine_details,
        "pickup_details": pickup_details,
        "admin_comments": admin_comments
    }

    try:
        # Validate the request body against the fixed schema
        validate(instance=service_body_data, schema=SERVICE_SCHEMA)
    except ValidationError as e:
        error_body={
            "message": 'Invalid request body',
            "errors":e.message,
            "RequiredSchema": SERVICE_SCHEMA,
            "status": 400
        }
        return error_body

    todo_ref = service_ref.document()
    todo_ref.set(service_body_data)
    success_body={
        "message": 'Service added successfully',
        "status": 200
    }
    return success_body

@app.route('/create-service', methods=['POST'])
@authenticate
def create_service(user):
    """
    POST a new service for the authenticated user.
    ---
    tags:
      - Services
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          $ref: '#/definitions/SERVICE_SCHEMA'  # Reference to the schema definition
    responses:
      201:
        description: Service added successfully
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
      SERVICE_SCHEMA: # Define the schema here
        type: object
        properties:
          sf_id:
            type: string
            description: Salesforce ID
          channel:
            type: string
            description: Channel of the service
          contact_details:
            type: object
            properties:
              first_name:
                type: string
                description: First name of the contact person
              last_name:
                type: string
                description: Last name of the contact person
              contact_numbers:
                type: object
                properties:
                  primary:
                    type: object
                    properties:
                      country_code:
                        type: number
                        description: Country code of the primary contact number
                      number:
                        type: number
                        description: Primary contact number
                      verified:
                        type: boolean
                        description: Flag indicating whether the primary contact number is verified
                      whatsapp:
                        type: boolean
                        description: Flag indicating whether the primary contact number is on WhatsApp
                  secondary:
                    type: object
                    properties:
                      country_code:
                        type: number
                        description: Country code of the secondary contact number
                      number:
                        type: number
                        description: Secondary contact number
                      verified:
                        type: boolean
                        description: Flag indicating whether the secondary contact number is verified
                      whatsapp:
                        type: boolean
                        description: Flag indicating whether the secondary contact number is on WhatsApp
                required:
                  - primary
                  - secondary
              email:
                type: string
                description: Email address of the contact person
              pickup_address:
                type: object
                properties:
                  address:
                    type: string
                    description: Address for pickup
                  city:
                    type: string
                    description: City for pickup
                  state:
                    type: string
                    description: State for pickup
                  pincode:
                    type: number
                    description: Pincode for pickup
                  google_location:
                    type: string
                    description: Google location for pickup
                required:
                  - address
                  - city
                  - state
                  - pincode
              use_differant_delivery_address:
                type: boolean
                description: Flag indicating whether a different delivery address is to be used
              delivery_address:
                type: object
                properties:
                  address:
                    type: string
                    description: Address for delivery
                  city:
                    type: string
                    description: City for delivery
                  state:
                    type: string
                    description: State for delivery
                  pincode: 
                    type: number
                    description: Pincode for delivery
                  google_location:
                    type: string
                    description: Google location for delivery
                required:
                  - address
                  - city
                  - state
                  - pincode
            required:
              - first_name
              - last_name
              - contact_numbers
              - pickup_address
              - delivery_address
          machine_details:
            type: object
            properties:
              item_brand:
                type: string
                description: Brand of the machine
              model:
                type: string
                description: Model of the machine
              item_category:
                type: string
                description: Category of the machine
              year_of_purchase:
                type: number
                description: Year of purchase of the machine
            required:
              - item_brand
              - model
              - item_category
              - year_of_purchase

          issue_message_from_customer:
            type: string
            description: Issue message from the customer
          admin_comments:
            type: array
            items:
              type: object
              properties:
                timestamp:
                  type: string
                  description: Timestamp of the comment
                user:
                  type: string
                  description: User who added the comment
                message:
                  type: string
                  description: Comment message
                required:
                  - timestamp
                  - user
                  - message
          delivery_note:
            type: string
            description: Delivery note
          pickup_details:
            type: object
            properties:
              pickup_note:
                type: string
                description: Pickup note
            required:
              - pickup_note
          self_logistics:
            type: boolean
            description: Flag indicating whether self logistics is used
        required:
          - sf_id
          - channel
          - contact_details
          - machine_details
          - issue_message_from_customer
          - admin_comments
          - delivery_note
          - pickup_details
          - self_logistics
    """

    try:
        data = request.json
        
        # Save the service to the database
        save_data_response = save_service_to_database(data, user)

        if save_data_response.get('status') == 400:
            return jsonify(save_data_response), 400
        else:
            return jsonify(save_data_response), 201

    except Exception as e:
        return jsonify({'error': 'Internal Server Error Saving Service', 'message': str(e)}), 500
    
## Get all the services
@app.route('/services', methods=['GET'])
@authenticate
def get_services(user):
    """
    Retrieve services for the authenticated user.
    ---
    tags:
      - Services
    security:
      - BearerAuth: []
    responses:
      200:
        description: Services retrieved successfully
        schema:
          type: object
          properties:
            services:
              type: array
              items:
                $ref: '#/definitions/SERVICE_SCHEMA'
      401:
        description: Unauthorized access
        schema:
          type: object
          properties:
            message:
              type: string
              description: Error message
    """
    try:
        services_ref = db.collection('service').stream()
        services = [{**service.to_dict(), "id": service.id} for service in services_ref]
        return jsonify({'services': services}), 200
    except Exception as e:
        return jsonify({'error': 'Internal Server Error Retrieving Services', 'message': str(e)}), 500

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
