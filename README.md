# 🎓 Excuse Pattern Recognition AI - Task Management System

A comprehensive AI-powered task management system that analyzes delay patterns, detects excuse repetition, and provides intelligent behavioral insights using machine learning and natural language processing.

## 🚀 Key Features

### � 5 Core AI Features

1. **Semantic Excuse Analysis (NLP)**
   - TF-IDF vectorization for text analysis
   - Cosine similarity for pattern detection
   - Detects repetitive excuses even with different wording
   - Originality scoring (0-100)

2. **Delay Risk Prediction (Machine Learning)**
   - Logistic Regression model
   - Predicts future delay probability
   - Binary classification (High/Low risk)
   - Trained on behavioral patterns

3. **Anomaly Detection (Unsupervised Learning)**
   - Isolation Forest algorithm
   - Detects sudden behavioral changes
   - Identifies outliers in delay patterns
   - Real-time anomaly flagging

4. **Time-Decay Trust Scoring**
   - Exponential time-decay weighting
   - Recent behavior weighted higher
   - Formula: `weight = exp(-0.05 × days_old)`
   - Dynamic trust score calculation

5. **WRS - Behavioral Reliability Score**
   - Composite AI metric
   - Components: Authenticity (60%), Risk (30%), Stability (+10)
   - Penalties for repetition and generic excuses
   - Single comprehensive reliability score

### � AI-Powered Analytics

- **Executive AI Summary** - Role-based professional interpretation
- **AI Intelligence Insights** - Color-coded severity analysis (critical/warning/stable)
- **Predictive Analytics** - ML-based delay forecasting
- **Behavioral Monitoring** - Real-time anomaly detection
- **Trust Trends** - Time-weighted reliability tracking

### 💼 Role-Based Access Control

- **Admin** - Full system access, user management, global analytics
- **Manager** - Team oversight, analytics, task assignment
- **Employee** - Personal tasks, delay submission, performance tracking

### 🎨 Modern UI Features

- Beautiful gradient designs with glassmorphism
- Interactive charts and gauges (Plotly.js)
- Real-time toast notifications
- Responsive dashboard layouts
- Dark mode optimized

## 🛠️ Technology Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: PostgreSQL
- **AI/ML Libraries**: 
  - scikit-learn (TF-IDF, Logistic Regression, Isolation Forest)
  - NumPy (numerical computations)
  - joblib (model persistence)

### Frontend
- **Templating**: Jinja2
- **Visualization**: Plotly.js
- **Styling**: Custom CSS with modern gradients
- **Icons**: Emoji-based (no external dependencies)

### Security
- CSRF protection
- Secure session management
- Password hashing (werkzeug)
- Role-based authorization

## � Installation

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- pip package manager

### Setup Instructions

1. **Clone the repository**
```bash
git clone <repository-url>
cd "final year"
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

Required packages:
- Flask
- psycopg2-binary (PostgreSQL adapter)
- scikit-learn (AI/ML features)
- numpy (numerical operations)
- joblib (model serialization)
- python-docx (report generation)
- reportlab (PDF export)

3. **Configure database**
Update `repository/db.py` with your PostgreSQL credentials:
```python
DB_CONFIG = {
    'dbname': 'your_database',
    'user': 'your_username',
    'password': 'your_password',
    'host': 'localhost',
    'port': 5432
}
```

4. **Initialize database**
Run the SQL schema from `schema.sql` to create tables.

5. **Run the application**
```bash
python run.py
```

The server will start at `http://127.0.0.1:5000`

## 🎯 Usage

### Default Login Credentials

**Admin Account:**
- Email: `admin@excuseai.com`
- Password: `Admin@2026`

**Manager Account:**
- Email: `manager@excuseai.com`
- Password: `Manager@2026`

**Employee Account:**
- Email: `employee@excuseai.com`
- Password: `Employee@2026`

### Core Workflows

1. **Task Assignment** (Admin/Manager)
   - Navigate to Dashboard
   - Click "Create Task"
   - Assign to employee with deadline

2. **Delay Submission** (Employee)
   - View assigned tasks
   - Click "Submit Delay" on task
   - Provide reason and optional proof
   - AI analyzes excuse and calculates scores

3. **Analytics Review** (All Roles)
   - Navigate to Analytics page
   - View AI-generated insights
   - Review Executive Summary
   - Analyze behavioral trends

4. **Report Export** (Admin/Manager)
   - Access Dashboard
   - Use Export Reports (CSV/WORD/PDF)
   - Download comprehensive analytics

## 🧠 AI Features Explained

### Why TF-IDF Instead of Deep Learning?

✅ **Lightweight** - No 80-120MB model downloads
✅ **Fast** - Instant startup, works offline
✅ **Practical** - Runs on low-spec laptops
✅ **Industry Standard** - Proven NLP technique
✅ **Easy to Explain** - Clear mathematical foundation

### Viva Defense Talking Points

**Q: How is this AI and not just a database application?**

A: "Our system uses multiple AI techniques:
- NLP for semantic text analysis (TF-IDF)
- Machine learning for predictive modeling (Logistic Regression)
- Unsupervised learning for anomaly detection (Isolation Forest)
- Intelligent scoring algorithms with time-decay weighting
These go beyond simple CRUD operations and demonstrate applied artificial intelligence."

**Q: What algorithms did you use?**

A: "We implemented:
- TF-IDF vectorization for NLP text analysis
- Logistic Regression for binary classification
- Isolation Forest for outlier detection
- Exponential time-decay for trust scoring
- Cosine similarity for pattern matching"

## 📁 Project Structure

```
final year/
├── ai_demo.py                 # 5 Core AI features implementation
├── app.py                     # Flask application factory
├── run.py                     # Application entry point
├── routes/                    # Route blueprints
│   ├── auth_routes.py        # Authentication
│   ├── task_routes.py        # Task management
│   ├── admin_routes.py       # Admin functions
│   └── analytics_routes.py   # Analytics endpoints
├── services/                  # Business logic
│   ├── analytics_service.py  # AI integration & analytics
│   ├── ai_insights.py        # Insights & summary generation
│   └── task_service.py       # Task operations
├── repository/               # Data access layer
│   └── db.py                # Database connection
├── templates/               # Jinja2 templates
│   ├── base.html           # Base layout
│   ├── dashboard.html      # Main dashboard
│   ├── analytics.html      # Analytics page
│   └── partials/           # Reusable components
└── static/                 # CSS, JS, assets
```

## 🎓 Academic Context

This project was developed as a final year college project demonstrating:
- Applied artificial intelligence
- Machine learning model training
- Natural language processing
- Full-stack web development
- Database design and optimization
- Security best practices

## 📊 Features Showcase

- ✅ Real NLP with TF-IDF vectorization
- ✅ ML model training and prediction
- ✅ Unsupervised anomaly detection
- ✅ Intelligent composite scoring
- ✅ Time-series analysis
- ✅ Role-based access control
- ✅ Interactive data visualization
- ✅ Automated report generation
- ✅ Modern responsive UI

## � Security Features

- CSRF token protection
- Secure password hashing
- Session-based authentication
- SQL injection prevention (parameterized queries)
- XSS protection (template escaping)
- Role-based authorization checks

## 📝 License

This project is developed for academic purposes.

## 👥 Contributors

Developed as a college final year project 

## Tools

- scikit-learn for ML algorithms
- Flask for web framework
- Plotly.js for visualizations
- PostgreSQL for database

---

**Note**: This is a demonstration project showcasing AI integration in task management. For production use, additional security hardening and scalability improvements would be recommended.
# Excuse-Pattern-Recognition
