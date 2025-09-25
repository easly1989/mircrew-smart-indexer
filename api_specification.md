# MIRCrew Smart Indexer API Specification

## New Endpoints

### 1. GET /api/thread/{threadId}/status
**Purpose**: Check thread status and like information  
**Parameters**:
- `threadId` (path): Forum thread ID
- `userId` (query): Optional user ID for personalized status

**Response**:
```json
{
  "thread_id": "12345",
  "like_count": 42,
  "user_liked": true,
  "last_updated": "2025-09-25T12:00:00Z",
  "cached": true
}
```

### 2. POST /api/thread/{threadId}/like
**Purpose**: Like/unlike a thread  
**Authentication**: Required  
**Parameters**:
- `threadId` (path): Forum thread ID
- `action` (body): "like" or "unlike"

**Response**:
```json
{
  "thread_id": "12345",
  "new_status": "liked",
  "total_likes": 43
}
```

### 3. GET /api/thread/{threadId}/releases
**Purpose**: Get releases from specific thread  
**Parameters**:
- `threadId` (path): Forum thread ID
- `season` (query): Optional season filter
- `episode` (query): Optional episode filter

**Response**: Torznab-compatible XML

### 4. GET /api/liked-threads
**Purpose**: List user's liked threads  
**Authentication**: Required  
**Parameters**:
- `page` (query): Pagination (default 1)
- `limit` (query): Items per page (default 25)

**Response**:
```json
{
  "results": [
    {
      "thread_id": "12345",
      "title": "Show Name S01",
      "like_date": "2025-09-25T11:30:00Z",
      "release_count": 5
    }
  ],
  "pagination": {
    "total": 42,
    "page": 1,
    "pages": 2
  }
}
```

### 5. POST /api/search/refresh/{threadId}
**Purpose**: Refresh cached thread data  
**Authentication**: Required (Admin)  
**Response**:
```json
{
  "thread_id": "12345",
  "refreshed_at": "2025-09-25T12:05:00Z",
  "new_releases": 2
}
```

## Database Schema Changes

### New Tables

#### 1. thread_likes
| Column       | Type        | Description                     |
|--------------|-------------|---------------------------------|
| id           | BIGSERIAL   | Primary key                     |
| thread_id    | VARCHAR(32) | Forum thread ID                 |
| user_id      | VARCHAR(64) | MirCrew user ID                 |
| liked_at     | TIMESTAMPTZ | When like was added             |
| unliked_at   | TIMESTAMPTZ | When like was removed (nullable)|

#### 2. cached_threads
| Column       | Type        | Description                     |
|--------------|-------------|---------------------------------|
| thread_id    | VARCHAR(32) | Primary key                     |
| title        | TEXT        | Thread title                    |
| author       | VARCHAR(64) | Thread author                   |
| post_date    | TIMESTAMPTZ | Original post date              |
| last_update  | TIMESTAMPTZ | Last metadata refresh           |
| like_count   | INTEGER     | Current like count              |

#### 3. like_history
| Column       | Type        | Description                     |
|--------------|-------------|---------------------------------|
| id           | BIGSERIAL   | Primary key                     |
| thread_id    | VARCHAR(32) | Forum thread ID                 |
| user_id      | VARCHAR(64) | MirCrew user ID                 |
| action       | VARCHAR(16) | "like" or "unlike"              |
| performed_at | TIMESTAMPTZ | Action timestamp                |
| ip_address   | INET        | User IP address                 |

## Authentication Flows

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant MirCrew Forum
    
    Client->>API: GET/POST (Read operation)
    alt New session
        API->>MirCrew Forum: Validate session cookie
        MirCrew Forum-->>API: Session status
        API->>Client: 401 if invalid
    else Write operation (like)
        API->>MirCrew Forum: Validate session + CSRF token
        MirCrew Forum-->>API: Authentication result
        API->>Client: 403 if invalid
    end
```

## Caching Strategy

| Data Type         | TTL    | Invalidation Triggers           | Storage         |
|-------------------|--------|----------------------------------|-----------------|
| Thread Metadata   | 24h    | Manual refresh, new releases    | Redis/PostgreSQL|
| Like Counts       | 1h     | Like/unlike actions             | Redis           |
| User Like Status  | 15m    | User like/unlike actions        | Redis           |
| Search Results    | 30m    | New thread creation             | Redis           |

## Migration Plan
1. Phase 1: Add new tables with zero-downtime migrations
2. Phase 2: Dual-write to old and new systems
3. Phase 3: Backfill existing like data (if any)
4. Phase 4: Switch read traffic to new endpoints
5. Phase 5: Deprecate old search endpoints
## Database Schema Diagram

```mermaid
erDiagram
    THREAD_LIKES ||--o{ CACHED_THREADS : "references"
    THREAD_LIKES ||--o{ LIKE_HISTORY : "records"
    CACHED_THREADS {
        string thread_id PK
        string title
        string author
        timestamp post_date
        timestamp last_update
        integer like_count
    }
    THREAD_LIKES {
        bigint id PK
        string thread_id FK
        string user_id
        timestamp liked_at
        timestamp unliked_at
    }
    LIKE_HISTORY {
        bigint id PK
        string thread_id FK
        string user_id
        string action
        timestamp performed_at
        inet ip_address
    }
```
## Authentication Flow Details

### Read Operations
```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthCache
    
    Client->>API: GET Request (No Auth)
    API->>AuthCache: Check session cookie
    alt Valid Session
        AuthCache-->>API: User info
        API->>Client: 200 OK with data
    else Invalid/Missing
        API->>Client: 401 Unauthorized
    end
```

### Write Operations (Like/Unlike)
```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthCache
    participant MirCrewForum
    
    Client->>API: POST Like (With CSRF Token)
    API->>AuthCache: Validate session + CSRF
    alt Valid
        API->>MirCrewForum: Perform action
        MirCrewForum-->>API: Success
        API->>Client: 200 OK
    else Invalid CSRF
        API->>Client: 403 Forbidden
    else Invalid Session
        API->>Client: 401 Unauthorized
    end
```

### Admin Operations
```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthCache
    participant AdminDB
    
    Client->>API: POST Refresh (Admin)
    API->>AuthCache: Validate session
    API->>AdminDB: Check admin privileges
    alt Valid Admin
        API->>MirCrewForum: Refresh data
        API->>Client: 200 OK
    else Not Admin
        API->>Client: 403 Forbidden
    end
```

## CSRF Protection Mechanism
1. Client obtains CSRF token via GET /api/csrf-token (cached for 1 hour)
2. Token must be included in X-CSRF-Token header for write operations
3. Server validates token against session-bound cache entry
## Caching Implementation Details

### Cache Layers
1. **Edge Cache (CDN)**: Static assets, API responses with public data
2. **Application Cache (Redis)**: 
   - Session data (TTL: 6h)
   - CSRF tokens (TTL: 1h)
   - Rate limit counters (Sliding window)
3. **Database Cache (Materialized Views)**:
   - Aggregated like counts
   - Popular threads

### Rate Limiting
```mermaid
flowchart TD
    A[Request] --> B{Write Operation?}
    B -->|Yes| C[Check Rate Limit]
    B -->|No| D[Process Request]
    C --> E{Rate Limit Exceeded?}
    E -->|Yes| F[429 Too Many Requests]
    E -->|No| D
```

### Cache Warming Strategy
1. **On Like/Unlike**: Update Redis counters immediately
2. **Scheduled Jobs**:
   - Hourly: Refresh popular thread metadata
   - Daily: Warm CDN cache for top 1000 threads
3. **On Refresh Command**: Full cache rebuild for specified thread

### Cache Invalidation
| Event                | Action                                  |
|----------------------|-----------------------------------------|
| New like             | Invalidate user-specific cache entries  |
| Thread update        | Invalidate thread metadata cache        |
| Admin refresh        | Full cache flush for thread             |
| Schema migration     | Global cache flush                      |