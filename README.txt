HOW TO DEPLOY (Free, 5 minutes)
================================

1. Go to https://render.com  →  Sign up free (use GitHub login)

2. Click "New +"  →  "Web Service"

3. Choose "Deploy from a Git repo"
   - If you don't have GitHub: click "Public Git repository"
   - Use this repo: https://github.com/render-examples/flask-hello-world
   - Actually: upload your files manually (see step 4)

EASIEST WAY — No GitHub needed:
4. Go to render.com → New + → Web Service → "Build and deploy from a Git repo"
   → Connect GitHub → Create a NEW repo called "xbox-tracker"
   → Upload server.py and requirements.txt to that repo
   → Render will auto-detect Python and deploy it

Settings on Render:
  - Build Command:  (leave empty)
  - Start Command:  python server.py
  - Plan: Free

5. After deploy you get a URL like:
   https://xbox-tracker.onrender.com
   
   Share that link — anyone on any phone can use it!
