# Drive API Documentation

Professional documentation for the Drive file sharing API.

## Features

- **Interactive Swagger UI**: Test endpoints directly in the browser
- **Complete OpenAPI 3.0 specification**: Industry-standard API documentation
- **Postman collection**: Ready-to-import collection for API testing
- **Professional design**: Clean, responsive documentation interface

## Quick Start

1. **View Documentation**:
   ```bash
   cd docs/
   chmod +x serve.sh
   ./serve.sh
   ```
   Open http://localhost:8080

2. **Import Postman Collection**:
   - Import `drive-api.postman_collection.json` into Postman
   - Set up environment variables for testing

3. **API Specification**:
   - Use `api-spec.yaml` with any OpenAPI-compatible tool
   - Generate client SDKs in multiple languages

## File Structure

```
docs/
├── api-spec.yaml              # OpenAPI specification
├── index.html                 # Documentation homepage
├── api.postman_collection.json  # Postman collection
├── serve.sh                   # Documentation server script
└── README.md                  # This file
```

## API Overview

The Drive API provides secure file sharing with the following capabilities:

- **Authentication**: Phone-based registration and JWT tokens
- **File Management**: Upload, download, and organize files
- **Exposure System**: Create time-limited public access to files
- **Access Control**: Request/approval workflow for file access
- **Security**: IP blacklisting and rate limiting

## User Types

- **Free Users**: 1 file exposure, 5-minute maximum duration
- **Premium Users**: Unlimited exposures, up to 24-hour duration

## Getting Started

1. Register with phone number
2. Login to receive access token
3. Upload files to your storage
4. Create exposures for sharing
5. Manage access requests and approvals

## Support

For API support and questions, refer to the interactive documentation at `/docs` endpoint when the API is running.