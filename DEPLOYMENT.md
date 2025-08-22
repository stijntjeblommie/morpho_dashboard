# 🚀 Deployment Guide for Morpho Blue Pool Analyzer

This guide covers multiple deployment options for the Streamlit dashboard, especially handling local JSON files.

## 📋 Table of Contents

1. [Local Development](#local-development)
2. [Streamlit Community Cloud](#streamlit-community-cloud)
3. [Docker Deployment](#docker-deployment)
4. [Cloud Platform Deployment](#cloud-platform-deployment)
5. [Handling Local JSON Files](#handling-local-json-files)
6. [Troubleshooting](#troubleshooting)

---

## 🏠 Local Development

### Quick Start (Recommended for Testing)
```bash
# 1. Navigate to your project directory
cd path/to/tool/

# 2. Install dependencies
pip install -r requirements.txt

# 3. Ensure you have your JSON files
ls *.json
# Should show: morpho_complete_analysis.json, pendle_morpho_summary.json, pendle_morpho_analysis.json

# 4. Run the dashboard
streamlit run morpho_dashboard.py
```

### Network Access (Share with Others on Same Network)
```bash
streamlit run morpho_dashboard.py --server.address 0.0.0.0 --server.port 8501
```
Access via: `http://YOUR_LOCAL_IP:8501` (e.g., `http://192.168.1.100:8501`)

---

## ☁️ Streamlit Community Cloud

**Best for sharing with others publicly/privately with GitHub integration.**

### Step 1: Prepare Your Repository

1. **Create a GitHub Repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/USERNAME/morpho-analyzer.git
   git push -u origin main
   ```

2. **Repository Structure Should Be:**
   ```
   your-repo/
   ├── morpho_dashboard.py
   ├── requirements.txt
   ├── config.json
   ├── README.md
   └── data/  # Create this folder for JSON files
       ├── morpho_complete_analysis.json
       ├── pendle_morpho_summary.json
       └── pendle_morpho_analysis.json
   ```

3. **Update File Paths in Code**
   Create a new file `morpho_dashboard_cloud.py`:
   ```python
   # At the top of the file, modify the load functions:
   
   def load_morpho_data(file_path: str = "data/morpho_complete_analysis.json") -> Dict:
       # ... rest of function stays the same
   
   def load_pendle_summary(file_path: str = "data/pendle_morpho_summary.json") -> Dict:
       # ... rest of function stays the same
   
   def load_pendle_analysis(file_path: str = "data/pendle_morpho_analysis.json") -> Dict:
       # ... rest of function stays the same
   ```

### Step 2: Deploy to Streamlit Cloud

1. **Go to** [share.streamlit.io](https://share.streamlit.io)
2. **Sign in** with your GitHub account
3. **Click "New app"**
4. **Configure:**
   - Repository: `USERNAME/morpho-analyzer`
   - Branch: `main`
   - Main file path: `morpho_dashboard_cloud.py`
5. **Click "Deploy"**

### Step 3: Handle JSON File Updates

**Option A: Manual Upload via GitHub**
```bash
# Update your JSON files locally, then:
git add data/*.json
git commit -m "Update data files"
git push origin main
# App will automatically redeploy
```

**Option B: File Upload Widget (Recommended)**
Add this to your Streamlit app:
```python
st.sidebar.markdown("## 📁 Upload Data Files")

uploaded_morpho = st.sidebar.file_uploader(
    "Upload Morpho Data", 
    type=['json'],
    key='morpho'
)

uploaded_pendle_summary = st.sidebar.file_uploader(
    "Upload Pendle Summary", 
    type=['json'],
    key='pendle_summary'
)

uploaded_pendle_analysis = st.sidebar.file_uploader(
    "Upload Pendle Analysis", 
    type=['json'],
    key='pendle_analysis'
)

if uploaded_morpho:
    morpho_data = json.load(uploaded_morpho)
else:
    morpho_data = load_morpho_data()  # fallback to file
```

---

## 🐳 Docker Deployment

**Best for consistent environments and self-hosting.**

### Create Dockerfile
```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Run Streamlit
CMD ["streamlit", "run", "morpho_dashboard.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true"]
```

### Build and Run
```bash
# Build the image
docker build -t morpho-analyzer .

# Run with JSON files mounted
docker run -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  morpho-analyzer
```

### Docker Compose (Recommended)
```yaml
# docker-compose.yml
version: '3.8'
services:
  morpho-dashboard:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./config.json:/app/config.json
    environment:
      - STREAMLIT_SERVER_HEADLESS=true
      - STREAMLIT_SERVER_PORT=8501
    restart: unless-stopped
```

Run with: `docker-compose up -d`

---

## 🌐 Cloud Platform Deployment

### Option 1: Railway

1. **Connect GitHub Repository**
2. **Add Environment Variables:**
   ```
   STREAMLIT_SERVER_HEADLESS=true
   STREAMLIT_SERVER_PORT=8501
   ```
3. **Deploy automatically on git push**

### Option 2: Heroku

1. **Create `Procfile`:**
   ```
   web: streamlit run morpho_dashboard.py --server.address 0.0.0.0 --server.port $PORT
   ```

2. **Create `setup.sh`:**
   ```bash
   mkdir -p ~/.streamlit/
   echo "\
   [general]\n\
   email = \"your-email@domain.com\"\n\
   " > ~/.streamlit/credentials.toml
   echo "\
   [server]\n\
   headless = true\n\
   enableCORS=false\n\
   port = $PORT\n\
   " > ~/.streamlit/config.toml
   ```

3. **Update `Procfile`:**
   ```
   web: sh setup.sh && streamlit run morpho_dashboard.py
   ```

### Option 3: DigitalOcean App Platform

1. **Create `.do/app.yaml`:**
   ```yaml
   name: morpho-analyzer
   services:
   - name: web
     source_dir: /
     github:
       repo: USERNAME/morpho-analyzer
       branch: main
     run_command: streamlit run morpho_dashboard.py --server.address 0.0.0.0 --server.port 8080
     environment_slug: python
     instance_count: 1
     instance_size_slug: basic-xxs
     http_port: 8080
   ```

---

## 📁 Handling Local JSON Files

### Strategy 1: File Upload Interface (Recommended)

Add this to your main dashboard:

```python
def load_data_with_upload():
    """Load data from files or uploads"""
    
    # Create upload interface
    st.sidebar.markdown("### 📁 Data Source")
    
    data_source = st.sidebar.radio(
        "Choose data source:",
        ["Local Files", "Upload Files"]
    )
    
    if data_source == "Upload Files":
        st.sidebar.markdown("**Upload your JSON files:**")
        
        morpho_file = st.sidebar.file_uploader(
            "Morpho Complete Analysis", 
            type=['json'],
            help="Upload morpho_complete_analysis.json"
        )
        
        pendle_summary_file = st.sidebar.file_uploader(
            "Pendle Summary", 
            type=['json'],
            help="Upload pendle_morpho_summary.json"
        )
        
        pendle_analysis_file = st.sidebar.file_uploader(
            "Pendle Analysis", 
            type=['json'], 
            help="Upload pendle_morpho_analysis.json"
        )
        
        # Load from uploads
        morpho_data = json.load(morpho_file) if morpho_file else {"data": []}
        pendle_summary = json.load(pendle_summary_file) if pendle_summary_file else {"ptMarkets": []}
        pendle_analysis = json.load(pendle_analysis_file) if pendle_analysis_file else {"ptMarketsData": {}}
        
    else:
        # Load from local files
        morpho_data = load_morpho_data()
        pendle_summary = load_pendle_summary() 
        pendle_analysis = load_pendle_analysis()
    
    return morpho_data, pendle_summary, pendle_analysis
```

### Strategy 2: GitHub Integration

```python
import requests

def load_data_from_github(repo_owner, repo_name, file_path):
    """Load JSON data from GitHub repository"""
    url = f"https://raw.githubusercontent.com/{repo_owner}/{repo_name}/main/{file_path}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except:
        return {}

# Usage
if not os.path.exists("morpho_complete_analysis.json"):
    st.info("Loading data from GitHub...")
    morpho_data = load_data_from_github("YOUR_USERNAME", "YOUR_REPO", "data/morpho_complete_analysis.json")
```

### Strategy 3: Cloud Storage Integration

```python
# For AWS S3
import boto3

def load_from_s3(bucket, key):
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj['Body'].read())

# For Google Cloud Storage
from google.cloud import storage

def load_from_gcs(bucket_name, blob_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return json.loads(blob.download_as_text())
```

---

## 🔧 Complete Deployment Example

### Modified Dashboard for Cloud Deployment

Create `morpho_dashboard_deployable.py`:

```python
import streamlit as st
import json
import os
from typing import Dict

# ... (all your existing imports and functions)

def load_data_sources():
    """Flexible data loading for different deployment scenarios"""
    
    st.sidebar.markdown("### 📊 Data Source")
    
    # Check what's available
    local_files_exist = all([
        os.path.exists("morpho_complete_analysis.json"),
        os.path.exists("pendle_morpho_summary.json"), 
        os.path.exists("pendle_morpho_analysis.json")
    ])
    
    data_files_exist = all([
        os.path.exists("data/morpho_complete_analysis.json"),
        os.path.exists("data/pendle_morpho_summary.json"),
        os.path.exists("data/pendle_morpho_analysis.json")
    ])
    
    if local_files_exist:
        st.sidebar.success("✅ Local files detected")
        return load_morpho_data(), load_pendle_summary(), load_pendle_analysis()
    
    elif data_files_exist:
        st.sidebar.success("✅ Data folder files detected")
        return (
            load_morpho_data("data/morpho_complete_analysis.json"),
            load_pendle_summary("data/pendle_morpho_summary.json"), 
            load_pendle_analysis("data/pendle_morpho_analysis.json")
        )
    
    else:
        st.sidebar.warning("⚠️ No local files found - please upload")
        
        # File upload interface
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            morpho_file = st.file_uploader(
                "Morpho Data", 
                type=['json'],
                key='morpho_upload'
            )
        
        with col2:
            pendle_summary_file = st.file_uploader(
                "Pendle Summary",
                type=['json'], 
                key='pendle_summary_upload'
            )
        
        pendle_analysis_file = st.sidebar.file_uploader(
            "Pendle Analysis",
            type=['json'],
            key='pendle_analysis_upload'
        )
        
        # Load from uploads or return empty
        morpho_data = json.load(morpho_file) if morpho_file else {"data": []}
        pendle_summary = json.load(pendle_summary_file) if pendle_summary_file else {"ptMarkets": []}
        pendle_analysis = json.load(pendle_analysis_file) if pendle_analysis_file else {"ptMarketsData": {}}
        
        return morpho_data, pendle_summary, pendle_analysis

# Update your main function
def main():
    st.title("🔵 Morpho Blue Pool Analyzer")
    st.markdown("Real-time analysis of Morpho Blue pools for yield strategies and leveraged looping opportunities")

    config = load_config()

    # Use flexible data loading
    with st.spinner("Loading data..."):
        morpho_data, pendle_summary, pendle_analysis = load_data_sources()

    if not morpho_data.get('data'):
        st.error("❌ No Morpho data available. Please upload data files or check file paths.")
        st.info("💡 Upload your JSON files using the sidebar, or ensure they exist in the correct location.")
        return

    # ... rest of your main function
```

---

## 🔍 Troubleshooting

### Common Issues

**1. "File not found" errors**
```python
# Add this debug information
if st.sidebar.checkbox("Debug Mode"):
    st.write("Current working directory:", os.getcwd())
    st.write("Files in directory:", os.listdir('.'))
    if os.path.exists('data'):
        st.write("Files in data directory:", os.listdir('data'))
```

**2. Memory issues with large JSON files**
```python
# Add file size limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def safe_json_load(file_obj):
    if file_obj.size > MAX_FILE_SIZE:
        st.error(f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024:.1f}MB")
        return None
    return json.load(file_obj)
```

**3. Port conflicts**
```bash
# Find and kill processes using port 8501
lsof -ti:8501 | xargs kill -9

# Use different port
streamlit run morpho_dashboard.py --server.port 8502
```

**4. Missing dependencies in deployment**
```python
# Add to requirements.txt
streamlit>=1.28.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.15.0
requests>=2.31.0
```

### Environment Variables for Production

Create `.env` file:
```bash
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_SERVER_ENABLE_CORS=false
STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

---

## 🏆 Recommended Deployment Strategy

**For Development/Personal Use:**
- Local deployment with `streamlit run morpho_dashboard.py`

**For Sharing with Team:**
- Streamlit Community Cloud with GitHub integration and file upload interface

**For Production/Public Use:**
- Docker deployment with automated data updates
- Cloud platform (Railway/DigitalOcean) with file upload interface

**For Enterprise:**
- Docker + Kubernetes with cloud storage integration
- Automated data pipeline for JSON updates

---

## 📝 Quick Deploy Checklist

- [ ] JSON files are in the correct location
- [ ] `requirements.txt` is complete
- [ ] Repository is pushed to GitHub (for cloud deployment)
- [ ] File paths are updated for deployment environment
- [ ] Upload interface is implemented (for public deployment)
- [ ] Environment variables are configured
- [ ] Health checks are working
- [ ] HTTPS is configured (for production)

---

**🎉 Your dashboard should now be successfully deployed and accessible!**

For additional support, check the [Streamlit documentation](https://docs.streamlit.io/streamlit-community-cloud) or create an issue in your repository.