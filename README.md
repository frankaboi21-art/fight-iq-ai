# ⚔️ Fight IQ AI

**Complete Martial Arts Intelligence Platform**

A production-ready full-stack application for analyzing fighter decision-making quality under pressure, with real-time tracking, AI-powered insights, and comprehensive training recommendations.

---

## 🚀 Features

### Core Analysis
- ✅ **6-Pillar Scoring System** - Distance Intelligence, Threat Recognition, Risk Management, Tactical Adaptation, Efficiency, Composure
- ✅ **32+ Mistake Taxonomy** - Categorized mistakes with danger ratings, coaching cues, and recommended drills
- ✅ **Pattern Detection** - Identify repeat offenses, fatigue patterns, and category trends
- ✅ **Priority Fix Algorithm** - Weighted recommendations based on impact and fix difficulty
- ✅ **Decision Trees** - Situational game plans triggered by specific mistakes

### Live Fight Tracking
- ✅ **Real-Time Scoring** - WebSocket-powered live updates
- ✅ **Momentum Tracking** - Dynamic momentum shifts based on performance
- ✅ **Win Probability** - Calculated probability based on current scores
- ✅ **AI Corner Advice** - Contextual coaching cues between rounds
- ✅ **Position Tracking** - Standing, clinch, guard, mount, back control

### Fighter Management
- ✅ **Fighter Profiles** - Career stats, Fight IQ trends, strengths/weaknesses
- ✅ **Historical Tracking** - Performance over time with trend analysis
- ✅ **Gym/Team Support** - Team management with leaderboards
- ✅ **Style Classification** - Pressure, Counter, Wrestler, Grappler, Striker, Balanced

### Social Features
- ✅ **Fight Predictions** - Make and track predictions with leaderboard
- ✅ **Comments** - Discuss analyses and predictions
- ✅ **Following** - Follow fighters and users
- ✅ **Achievements** - Badges for prediction streaks and milestones

### Production Ready
- ✅ **JWT Authentication** - Secure token-based auth with refresh tokens
- ✅ **API Key Support** - For programmatic access
- ✅ **PostgreSQL Database** - SQLAlchemy ORM with migrations
- ✅ **Redis Caching** - High-performance caching layer
- ✅ **Docker Deployment** - Multi-stage production builds
- ✅ **Nginx Reverse Proxy** - SSL, rate limiting, WebSocket support
- ✅ **Comprehensive Tests** - 50+ pytest tests with coverage

---

## 📊 The 6 Pillars of Fight IQ

| Pillar | Weight | Description |
|--------|--------|-------------|
| 🎯 Distance Intelligence | 20% | Range management and positioning |
| 👁️ Threat Recognition | 20% | Reading and reacting to danger |
| 🛡️ Risk Management | 20% | Avoiding unnecessary danger |
| 🔄 Tactical Adaptation | 15% | Adjusting strategy mid-fight |
| ⚡ Efficiency | 15% | Energy and output management |
| 🧘 Composure | 10% | Mental control under pressure |

---

## 🛠️ Quick Start

### Option 1: Development (Easiest)

```bash
# Clone and setup
git clone https://github.com/your-org/fight-iq-pro.git
cd fight-iq-pro

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m app.main
```

Open http://localhost:8000 in your browser.

### Option 2: Docker Compose (Production)

```bash
# Build and run all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Option 3: Docker (API Only)

```bash
# Build image
docker build -t fight-iq-pro .

# Run container
docker run -p 8000:8000 fight-iq-pro
```

---

## 📚 API Documentation

Once running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/analysis` | Create fight analysis |
| `GET` | `/api/v1/analysis/{id}` | Get analysis by ID |
| `GET` | `/api/v1/analysis/demo` | Run demo analysis |
| `POST` | `/api/v1/live` | Start live fight tracking |
| `POST` | `/api/v1/live/{id}/mistake` | Log mistake in live fight |
| `POST` | `/api/v1/live/{id}/round` | Advance round |
| `POST` | `/api/v1/fighters` | Create fighter |
| `GET` | `/api/v1/fighters` | List fighters |
| `POST` | `/api/v1/scout` | Create scouting report |
| `GET` | `/api/v1/mistakes` | Get mistake taxonomy |
| `GET` | `/api/v1/trees` | Get decision trees |
| `WS` | `/ws/live/{id}` | Live fight WebSocket |

### Example: Create Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{
    "mistakes": [
      {"mistake_id": "DEF_001", "severity": "critical", "round": 1},
      {"mistake_id": "DEF_002", "severity": "risky", "round": 2},
      {"mistake_id": "COMP_001", "severity": "critical", "round": 3}
    ]
  }'
```

### Example Response

```json
{
  "analysis_id": "abc123",
  "overall_score": 72.5,
  "grade": "C+",
  "pillar_scores": {
    "distance_intelligence": {"score": 85.0, "mistakes": 1, "weight": 0.20},
    "threat_recognition": {"score": 65.0, "mistakes": 2, "weight": 0.20},
    ...
  },
  "priority_fix": {
    "mistake_id": "DEF_001",
    "name": "Chin Exposed",
    "coaching_cue": "Chin down, eyes up through eyebrows",
    "drills": ["Tennis ball chin drill", "Mirror shadowboxing"]
  }
}
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api.py -v

# Run specific test
pytest tests/test_api.py::TestScoringEngine::test_severity_multipliers -v
```

---

## 🏗️ Project Structure

```
fight_iq_pro/
├── app/
│   ├── api/v1/              # API route handlers
│   │   └── endpoints/       # Organized by feature
│   ├── core/                # Core configurations
│   │   ├── config.py        # Application settings
│   │   ├── database.py      # Database connection
│   │   └── security.py      # Auth & security
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   │   └── scoring_engine.py # Core scoring algorithm
│   ├── websockets/          # WebSocket handlers
│   │   └── manager.py       # Connection management
│   └── main.py              # FastAPI application
├── frontend/
│   └── src/
│       └── components/      # React components
├── tests/
│   ├── test_api.py          # API tests
│   └── conftest.py          # Test fixtures
├── scripts/                 # Utility scripts
├── docs/                    # Additional documentation
├── migrations/              # Alembic migrations
├── docker-compose.yml       # Docker orchestration
├── Dockerfile               # Container build
├── nginx.conf               # Reverse proxy config
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/fightiq

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Pillar Weight Customization

Adjust pillar weights in `app/core/config.py`:

```python
PILLAR_DISTANCE_INTELLIGENCE: float = 0.20
PILLAR_THREAT_RECOGNITION: float = 0.20
PILLAR_RISK_MANAGEMENT: float = 0.20
PILLAR_TACTICAL_ADAPTATION: float = 0.15
PILLAR_EFFICIENCY: float = 0.15
PILLAR_COMPOSURE: float = 0.10
```

---

## 🔧 Development

### Adding New Mistakes

1. Add to `MISTAKES` dictionary in `app/services/scoring_engine.py`:

```python
"DEF_009": {
    "id": "DEF_009",
    "name": "New Mistake",
    "category": "defensive",
    "primary_pillar": "threat_recognition",
    "secondary_pillar": None,
    "danger_rating": 3,
    "outcome_impact": 3,
    "fix_difficulty": 2,
    "coaching_cue": "Coaching advice here",
    "drills": ["Drill 1", "Drill 2"],
    "counter_exploitation": "How opponent can exploit",
    "fatigue_correlation": 0.5,
},
```

### Adding New Decision Trees

Add to `DECISION_TREES` dictionary:

```python
"new_tree": {
    "id": "new_tree",
    "name": "New Decision Tree",
    "triggers": ["DEF_001", "DEF_002"],
    "primary_pillar": "threat_recognition",
    "branches": [
        {
            "situation": "When X happens",
            "primary_response": "Do Y",
            "secondary_response": "Alternative Z",
            "key_point": "Remember this",
        },
    ],
},
```

---

## 🚀 Deployment

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure PostgreSQL with SSL
- [ ] Set up Redis with password
- [ ] Configure SSL certificates in Nginx
- [ ] Enable rate limiting
- [ ] Set up monitoring (Sentry, Prometheus)
- [ ] Configure backups
- [ ] Review CORS origins

### Docker Production Deploy

```bash
# Build production image
docker-compose -f docker-compose.yml build

# Start services
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# Check health
curl http://localhost/api/v1/health
```

---

## 📈 Performance

### Benchmarks (MacBook Pro M2, 8GB RAM)

| Operation | Time |
|-----------|------|
| Health check | < 5ms |
| Analysis (10 mistakes) | < 20ms |
| Live fight update | < 15ms |
| WebSocket broadcast | < 5ms |

### Scaling Recommendations

- **API**: Horizontal scaling with load balancer
- **Database**: Read replicas for heavy loads
- **Redis**: Cluster mode for high throughput
- **WebSockets**: Sticky sessions or pub/sub

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- UI components with [React](https://reactjs.org/)
- Styling with [Tailwind CSS](https://tailwindcss.com/)
- Database ORM by [SQLAlchemy](https://www.sqlalchemy.org/)

---

**Made with ⚔️ for the martial arts community**
