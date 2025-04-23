# CSV Scanner Application Architecture

## System Overview

```mermaid
graph TB
    subgraph Client Layer
        C[Web Browser]
        M[Mobile Browser]
    end

    subgraph AWS Cloud
        subgraph EC2 Instance
            subgraph Application Layer
                N[Nginx Reverse Proxy]
                G[Gunicorn WSGI Server]
                F[Flask Application]
            end

            subgraph Data Processing Layer
                P[Pandas CSV Processor]
                B[AWS Bedrock Integration]
            end

            subgraph Storage Layer
                V[Virtual Environment]
                E[Environment Variables]
            end
        end

        subgraph AWS Services
            BR[AWS Bedrock]
            S3[AWS S3]
            CW[CloudWatch]
        end
    end

    C --> N
    M --> N
    N --> G
    G --> F
    F --> P
    F --> B
    B --> BR
    P --> S3
    F --> E
    F --> V
    BR --> CW
```

## Component Details

### Client Layer

- **Web Browser**: Standard web interface for desktop users
- **Mobile Browser**: Responsive interface for mobile users

### Application Layer

- **Nginx (Port 80)**:

  - Reverse proxy
  - SSL/TLS termination
  - Static file serving
  - Load balancing

- **Gunicorn (Port 8000)**:

  - WSGI server
  - 4 worker processes
  - Process management
  - Request handling

- **Flask Application**:
  - Web framework
  - Route handling
  - Request processing
  - Response generation

### Data Processing Layer

- **Pandas**:

  - CSV file parsing
  - Data manipulation
  - Status determination
  - Data analysis

- **AWS Bedrock Integration**:
  - Natural language processing
  - Query understanding
  - Response generation
  - AWS API communication

### Storage Layer

- **Virtual Environment**:

  - Python dependencies
  - Isolated runtime
  - Package management

- **Environment Variables**:
  - AWS credentials
  - Configuration settings
  - Security parameters

### AWS Services

- **AWS Bedrock**:

  - AI/ML capabilities
  - Natural language understanding
  - Response generation

- **AWS S3**:

  - File storage
  - Data persistence
  - Backup storage

- **CloudWatch**:
  - Logging
  - Monitoring
  - Metrics collection

## Security Architecture

```mermaid
graph LR
    subgraph Security Measures
        SSL[SSL/TLS Encryption]
        SG[Security Groups]
        IAM[IAM Roles]
        ENV[Environment Variables]
    end

    subgraph Access Control
        IP[IP Restrictions]
        UFW[UFW Firewall]
        KEY[SSH Key Authentication]
    end

    SSL --> SG
    SG --> IAM
    IAM --> ENV
    IP --> UFW
    UFW --> KEY
```

## Deployment Architecture

```mermaid
graph TB
    subgraph Deployment Process
        GIT[Git Repository]
        CI[CI/CD Pipeline]
        DEP[Deployment Script]
    end

    subgraph EC2 Setup
        INIT[Instance Initialization]
        CONF[Service Configuration]
        MON[Monitoring Setup]
    end

    GIT --> CI
    CI --> DEP
    DEP --> INIT
    INIT --> CONF
    CONF --> MON
```

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Nginx
    participant Gunicorn
    participant Flask
    participant Pandas
    participant Bedrock
    participant S3

    User->>Nginx: Upload CSV
    Nginx->>Gunicorn: Forward Request
    Gunicorn->>Flask: Process Request
    Flask->>Pandas: Parse CSV
    Pandas->>S3: Store Data
    User->>Nginx: Submit Query
    Nginx->>Gunicorn: Forward Query
    Gunicorn->>Flask: Process Query
    Flask->>Bedrock: Send Query
    Bedrock-->>Flask: Generate Response
    Flask-->>Gunicorn: Return Response
    Gunicorn-->>Nginx: Forward Response
    Nginx-->>User: Display Result
```
