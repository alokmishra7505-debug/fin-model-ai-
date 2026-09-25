# Free deployment: GitHub + Streamlit Community Cloud

## 1. Create the GitHub repository

Create a new repository, for example `finmodel-ai`.

Recommended visibility for an interview portfolio: **Public**, unless you want to keep the source private. Streamlit Community Cloud can also access private repositories after authorization.

Upload the complete contents of this folder so that `streamlit_app.py`, `requirements.txt`, and `finmodel_agents/` are at the repository root.

## 2. Deploy

Go to Streamlit Community Cloud and sign in with GitHub.

Choose **Create app** → **Yup, I have an app**.

Select:
- Repository: your `finmodel-ai` repo
- Branch: `main`
- Main file path: `streamlit_app.py`

Choose a readable app subdomain if available, then deploy.

## 3. Test before an interview

Run at least one company end-to-end and verify:
- historical statements load
- forecasts render
- DCF/sensitivity render
- model checks are visible
- complete Excel model downloads

Keep one downloaded Excel model locally as a fallback in case public market-data requests are temporarily throttled during the interview.

## 4. What to share

Use three links/items:
1. Live Streamlit app
2. GitHub repository
3. One sample Excel model (Google Drive or GitHub Release) plus dashboard screenshots
