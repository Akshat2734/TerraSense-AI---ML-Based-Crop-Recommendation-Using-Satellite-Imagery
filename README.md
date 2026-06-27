# 🌱 TerraSense AI - ML-Based Crop Recommendation & Precision Agriculture

> Distributed ML-powered precision agriculture platform built with
> **FastAPI, PyQt6, PyTorch, LightGBM, PostGIS, Celery, RabbitMQ, Redis,
> Docker, and Nginx**.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Docker](https://img.shields.io/badge/Docker-Containerized-blue)
![Redis](https://img.shields.io/badge/Redis-Cache-red)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-Queue-orange)
![PostGIS](https://img.shields.io/badge/PostGIS-Geospatial-success)

------------------------------------------------------------------------

# 📖 Table of Contents

-   Overview
-   Features
-   Architecture
-   Machine Learning Pipeline
-   Infrastructure
-   Request Lifecycle
-   Database
-   Technology Stack
-   Folder Structure
-   Installation
-   Docker Deployment
-   Scalability
-   Monitoring
-   Future Improvements

------------------------------------------------------------------------

# 🌟 Overview

TerraSense AI is a distributed precision agriculture platform that
combines deep learning, geospatial intelligence, and environmental data
to recommend optimal crops. Heavy inference workloads are processed
asynchronously using Celery workers while Redis, RabbitMQ, PgBouncer,
and PostGIS provide a scalable backend.

------------------------------------------------------------------------

# 🚀 Features

-   PyQt6 desktop client
-   FastAPI backend
-   EfficientNet-B0 soil classifier
-   LightGBM crop recommendation
-   Google Earth Engine NDVI retrieval
-   NASA POWER weather integration
-   PostGIS polygon storage
-   Redis caching (24-hour TTL)
-   RabbitMQ task queue
-   Celery background workers
-   WebSocket live updates
-   Docker Compose deployment
-   Prometheus & Grafana monitoring

------------------------------------------------------------------------

# 🏗️ High Level Architecture

``` mermaid
graph TD
    Client[PyQt6 Desktop Client] -->|REST/WebSocket| Nginx[Nginx Gateway]

    Nginx --> API[FastAPI Cluster]

    API -->|Read History| DB[(PostGIS)]
    API -->|Queue Task| Rabbit[(RabbitMQ)]

    Rabbit --> Worker[Celery Worker]

    Worker --> NASA[NASA POWER API]
    Worker --> GEE[Google Earth Engine]

    Worker --> CNN[EfficientNet-B0]
    Worker --> LGBM[LightGBM]

    Worker --> PgB[PgBouncer]
    PgB --> DB

    Worker --> Redis[(Redis)]

    Redis --> API

    API --> Client
```

------------------------------------------------------------------------

# 🧠 Machine Learning Pipeline

``` mermaid
flowchart LR

Image[Satellite/Soil Image]
--> CNN[EfficientNet-B0]

CNN --> Soil[Detected Soil]

Weather[NASA POWER]
--> Features

NDVI[Google Earth Engine]
--> Features

Soil --> Features

Features --> LGBM[LightGBM]

LGBM --> Crop[Recommended Crop]
```

------------------------------------------------------------------------

# 🔄 Request Lifecycle

``` mermaid
sequenceDiagram

participant User
participant Client
participant API
participant Redis
participant Rabbit
participant Worker
participant DB

User->>Client: Submit image + NPK + Location

Client->>API: POST /predict

API->>Redis: Cache Lookup

alt Cache Hit
Redis-->>API: Prediction
API-->>Client: Return Result

else Cache Miss

API->>Rabbit: Publish Task

Rabbit->>Worker: Consume Task

Worker->>Worker: CNN Prediction

Worker->>Worker: Weather + NDVI

Worker->>Worker: LightGBM Prediction

Worker->>DB: Save Prediction

Worker->>Redis: Cache Result

API-->>Client: Task Completed

end
```

------------------------------------------------------------------------

# 🗄️ Entity Relationship Diagram

``` mermaid
erDiagram

USERS {
int id PK
string email
string hashed_password
}

PREDICTIONS{
int id PK
int user_id FK
string detected_soil
string recommended_crop
float satellite_ndvi
geometry location
datetime created_at
}

USERS ||--o{ PREDICTIONS : has_many
```

------------------------------------------------------------------------

# 🌐 Infrastructure Topology

``` mermaid
graph TB

subgraph Client
Desktop[PyQt6]
end

subgraph Gateway
Nginx
end

subgraph Backend
API1[FastAPI]
Worker[Celery]
end

subgraph Services
Redis
RabbitMQ
PgBouncer
PostGIS
end

subgraph External
NASA
GEE
end

Desktop-->Nginx
Nginx-->API1
API1-->RabbitMQ
RabbitMQ-->Worker
Worker-->NASA
Worker-->GEE
Worker-->PgBouncer
PgBouncer-->PostGIS
Worker-->Redis
Redis-->API1
```

------------------------------------------------------------------------

# 🗂️ Project Structure

``` text
TerraSense-AI/

client/
├── ui/
├── widgets/
├── assets/

server/
├── api/
├── models/
├── workers/
├── services/
├── database/

docker/
nginx/
prometheus/
grafana/

docker-compose.yml
README.md
```

------------------------------------------------------------------------

# 💻 Technology Stack

  Layer        Technologies
  ------------ ---------------------
  Frontend     PyQt6
  Backend      FastAPI
  ML           PyTorch, LightGBM
  Database     PostgreSQL, PostGIS
  Cache        Redis
  Queue        RabbitMQ
  Workers      Celery
  Gateway      Nginx
  DevOps       Docker Compose
  Monitoring   Prometheus, Grafana

------------------------------------------------------------------------

# ⚙️ Installation

``` bash
git clone <repository>

cd TerraSense-AI
```

Install dependencies

``` bash
pip install -r requirements.txt
```

Run using Docker

``` bash
docker compose up --build
```

------------------------------------------------------------------------

# 📦 Services

-   FastAPI API
-   Celery Worker
-   RabbitMQ
-   Redis
-   PostGIS
-   PgBouncer
-   Nginx
-   Prometheus
-   Grafana

------------------------------------------------------------------------

# 📈 Scalability

-   Redis 24-hour response caching
-   PgBouncer connection pooling
-   RabbitMQ asynchronous task queue
-   Celery worker scaling
-   Kubernetes HPA compatible
-   Stateless FastAPI containers

------------------------------------------------------------------------

# 📊 Monitoring

-   Prometheus metrics
-   Grafana dashboards
-   Queue monitoring
-   API latency
-   Worker throughput
-   Database performance

------------------------------------------------------------------------

# 🔒 Security

-   Password hashing
-   JWT authentication
-   Environment variables
-   Connection pooling
-   Input validation
-   Docker network isolation

------------------------------------------------------------------------

# 🚀 Future Improvements

-   Kubernetes deployment
-   Multi-region support
-   GPU inference workers
-   Model versioning
-   Kafka event streaming
-   Mobile application
-   Multi-language support
