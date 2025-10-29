# Mac Setup Instructions

## 🚀 Super Quick Setup (Just 2 Commands!)

### Step 1: Download All Files
Download all files from the links provided to a folder on your Mac (e.g., `~/Downloads/shopify-uploader/`)

### Step 2: Run Setup Script
Open Terminal and run:

```bash
cd ~/Downloads/shopify-uploader
chmod +x setup.sh
./setup.sh
```

**That's it!** 🎉 The script does everything automatically:
- ✅ Creates all directories (docs, input, output, logs)
- ✅ Moves documentation files to docs/ folder
- ✅ Creates .gitignore file
- ✅ Checks Python version (requires 3.7+)
- ✅ Installs all Python dependencies (ttkbootstrap, requests)
- ✅ Verifies installation

---

## 📋 What the Setup Script Does

The `setup.sh` script is comprehensive and handles everything:

1. **Checks Environment**
   - Verifies all required files are present
   - Checks Python installation
   - Validates Python version (3.7+)

2. **Creates Directory Structure**
   - `docs/` - All documentation files
   - `input/` - Your product JSON files
   - `output/` - Results from processing
   - `logs/` - Processing logs

3. **Organizes Files**
   - Moves all .md files to docs/
   - Keeps main script in root
   - Creates .gitignore to protect credentials

4. **Installs Dependencies**
   - Automatically runs `pip install -r requirements.txt`
   - Installs ttkbootstrap and requests
   - Verifies packages are working

5. **Final Verification**
   - Tests that packages import correctly
   - Shows you the final directory structure
   - Provides next steps

---

## 📂 Final Directory Structure

After running the setup script:

```
shopify-product-uploader/
├── shopify_product_uploader.py    ← Main script
├── requirements.txt                ← Dependencies (installed!)
├── config_sample.json             ← Example config
├── setup.sh                       ← Setup script
├── .gitignore                     ← Git ignore rules
├── docs/                          ← Documentation
│   ├── README.md
│   ├── QUICK_START.md
│   ├── TECHNICAL_DOCS.md
│   ├── DEPLOYMENT_GUIDE.md
│   └── CHANGELOG.md
├── input/                         ← Your JSON files go here
├── output/                        ← Results saved here
└── logs/                          ← Logs saved here
```

---

## 🎯 After Setup - Quick Start

```bash
# 1. View the quick start guide
cat docs/QUICK_START.md

# 2. Place your product JSON in input folder
mv ~/Downloads/techo_bloc_products.json input/

# 3. Run the application
python3 shopify_product_uploader.py
```

In the GUI:
1. Click **⚙️ Settings** → Enter Shopify credentials → Save
2. Select **Input File** from input/ folder
3. Choose **Output File** and **Log File** locations
4. Click **Validate Settings**
5. Click **Start Processing**

---

## 🔧 Troubleshooting

### Setup Script Issues

**"Permission denied" error:**
```bash
chmod +x setup.sh
./setup.sh
```

**"shopify_product_uploader.py not found":**
- Make sure all files are downloaded to the same directory
- Navigate to that directory before running setup.sh:
  ```bash
  cd ~/Downloads/shopify-uploader
  ls -la
  ./setup.sh
  ```

### Python Issues

**"Python not found":**
```bash
brew install python3
```

**"Python version X.X is too old":**
```bash
brew upgrade python3
```

**"pip not found":**
```bash
python3 -m pip install -r requirements.txt
```

### Package Installation Issues

**Installation fails:**
```bash
pip3 install --user -r requirements.txt
```

**Verify installation:**
```bash
python3 -c "import ttkbootstrap; import requests; print('OK')"
```

---

## 🌟 Using a Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python shopify_product_uploader.py
deactivate
```

---

## 📖 Next Steps

1. **Read Documentation**
   ```bash
   cat docs/QUICK_START.md
   cat docs/README.md
   ```

2. **Get Shopify Credentials**
   - Shopify Admin → Apps → Develop apps
   - Create app with scopes: `write_products`, `write_files`

3. **Run the Application**
   ```bash
   python3 shopify_product_uploader.py
   ```

---

## ✨ Summary

**Quick Setup:**
```bash
cd ~/Downloads/shopify-uploader
chmod +x setup.sh
./setup.sh
```

**Run Application:**
```bash
python3 shopify_product_uploader.py
```

**That's all you need!** 🚀
