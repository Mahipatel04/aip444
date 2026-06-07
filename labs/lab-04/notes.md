# Introduction to APIs and HTTP

## What is an API?
An Application Programming Interface (API) is a way for two programs to talk to each other.
APIs define the rules for how requests and responses should be structured.

## HTTP Methods
- GET: Retrieve data from a server. Does not modify anything.
- POST: Send data to a server to create a new resource.
- PUT: Update an existing resource completely.
- DELETE: Remove a resource from the server.

## Status Codes
- 200 OK: The request was successful.
- 201 Created: A new resource was successfully created.
- 400 Bad Request: The client sent invalid data.
- 401 Unauthorized: Authentication is required.
- 404 Not Found: The requested resource does not exist.
- 500 Internal Server Error: Something went wrong on the server side.

## JSON
JavaScript Object Notation (JSON) is the most common format for sending data between
a client and a server. It uses key-value pairs and is easy for both humans and machines to read.
Tokens stored in localStorage are accessible to any JavaScript on the page, making them
vulnerable to Cross-Site Scripting (XSS) attacks.

## REST APIs
Representational State Transfer (REST) is a set of rules for designing APIs.
REST APIs are stateless, meaning each request must contain all the information needed
to process it. The server does not remember previous requests.