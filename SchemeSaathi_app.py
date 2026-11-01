import hashlib, hmac, secrets, re, sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="SchemeSaathi | Government Scheme Finder", page_icon="🇮🇳", layout="wide")
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "schemes.csv"
DB_PATH = BASE_DIR / "schemesaathi_users.db"
ITERATIONS = 200_000

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:Inter,sans-serif}
.stApp{background:#f5f7fb}.block-container{max-width:1200px;padding-top:2rem}
.hero{padding:2rem;border-radius:18px;color:white;background:linear-gradient(120deg,#123b70,#176b87);margin-bottom:1.3rem}
.hero h1{color:white;margin:0}.hero p{color:#e6f4ff;margin:.5rem 0 0}
div[data-testid="stMetric"]{background:white;padding:1rem;border-radius:14px;border:1px solid #e5eaf2}
</style>
""", unsafe_allow_html=True)

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()

def create_user(name, email, password):
    salt = secrets.token_hex(16)
    hashed = password_hash(password, salt)
    try:
        with db() as conn:
            conn.execute("INSERT INTO users(full_name,email,salt,password_hash) VALUES(?,?,?,?)",
                         (name.strip(), email.strip().lower(), salt, hashed))
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(email, password):
    with db() as conn:
        row = conn.execute("SELECT id,full_name,email,salt,password_hash FROM users WHERE email=? COLLATE NOCASE",
                           (email.strip().lower(),)).fetchone()
    if not row:
        return None
    uid, name, saved_email, salt, saved_hash = row
    if hmac.compare_digest(password_hash(password, salt), saved_hash):
        return {"id": uid, "full_name": name, "email": saved_email}
    return None

def render_auth():
    st.markdown('<div class="hero"><h1>🇮🇳 SchemeSaathi</h1><p>Discover government schemes and support programmes that may fit your profile.</p></div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.subheader("Welcome")
        st.write("Sign in to continue, or create a free account.")
        mode = st.radio("Account", ["Sign in", "Create account"], horizontal=True)
        if mode == "Sign in":
            with st.form("login_form"):
                email = st.text_input("Email address")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign in", use_container_width=True)
            if submit:
                if not email.strip() or not password:
                    st.error("Enter both your email and password.")
                else:
                    user = verify_user(email, password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Incorrect email or password.")
        else:
            with st.form("register_form"):
                name = st.text_input("Full name")
                email = st.text_input("Email address")
                password = st.text_input("Create password", type="password")
                confirm = st.text_input("Confirm password", type="password")
                submit = st.form_submit_button("Create account", use_container_width=True)
            if submit:
                if not name.strip() or not email.strip() or not password:
                    st.error("Please complete all fields.")
                elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
                    st.error("Enter a valid email address.")
                elif len(password) < 8:
                    st.error("Password must contain at least 8 characters.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                elif create_user(name, email, password):
                    st.success("Account created. Now select Sign in.")
                else:
                    st.error("An account with this email already exists.")
        st.caption("Student prototype. Use a unique password; do not enter Aadhaar or bank details.")

EXPECTED = ["name","description","benefit","min_age","max_age","state","occupation","max_income",
            "category","gender","official_url","scheme_type","keywords","source_note"]

@st.cache_data
def load_schemes():
    if not DATA_PATH.exists():
        raise FileNotFoundError("schemes.csv must be in the same folder as app.py.")
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    df.columns = [str(c).strip().lower() for c in df.columns]
    # Add optional columns when an older CSV does not contain them.
    for col in EXPECTED:
        if col not in df.columns:
            df[col] = ""
    for col in EXPECTED:
        if col not in ("min_age","max_age"):
            df[col] = df[col].fillna("").astype(str).str.strip()
    df["min_age"] = pd.to_numeric(df["min_age"], errors="coerce").fillna(0).astype(int)
    df["max_age"] = pd.to_numeric(df["max_age"], errors="coerce").fillna(100).astype(int)
    return df[EXPECTED]

def profile_match(row, age, state, occupation, income, category, gender):
    checks = [
        (age >= row["min_age"], f"Minimum age: {row['min_age']}"),
        (age <= row["max_age"], f"Maximum age: {row['max_age']}"),
    ]
    for field, value, label in [
        ("state", state, "State"),
        ("occupation", occupation, "Occupation"),
        ("category", category, "Category"),
        ("gender", gender, "Gender"),
    ]:
        scheme_value = str(row[field]).strip()
        ok = scheme_value.lower() in ("", "any", "all", "all india", "all states") or scheme_value.lower() == str(value).lower()
        checks.append((ok, f"{label}: {scheme_value or 'No restriction'}"))
    limit = str(row["max_income"]).strip().replace(",", "").replace("₹", "")
    if limit.lower() in ("", "none", "nan", "null", "no limit"):
        checks.append((True, "No income limit listed"))
    else:
        try:
            checks.append((income <= float(limit), f"Listed income limit: ₹{float(limit):,.0f}"))
        except ValueError:
            checks.append((True, "Income limit needs verification"))
    passed = sum(ok for ok, _ in checks)
    return passed, len(checks), [reason for ok, reason in checks if ok], all(ok for ok, _ in checks)

init_db()
if "user" not in st.session_state:
    st.session_state.user = None
if not st.session_state.user:
    render_auth()
    st.stop()

user = st.session_state.user
st.markdown('<div class="hero"><h1>🇮🇳 SchemeSaathi</h1><p>Find government schemes that may fit your profile.</p></div>', unsafe_allow_html=True)
with st.sidebar:
    st.markdown(f"### Welcome, {user['full_name']}")
    st.caption(user["email"])
    if st.button("Log out", use_container_width=True):
        st.session_state.user = None
        st.rerun()
    st.divider()
    st.header("Your profile")
    age = st.slider("Age", 1, 100, 21)
    state = st.selectbox("State / UT", ["Karnataka","Maharashtra","Telangana","Andhra Pradesh","Tamil Nadu","Kerala","Goa","Delhi","Uttar Pradesh","Other"])
    occupation = st.selectbox("Occupation", ["Student","Farmer","Worker","Entrepreneur","Unemployed","Other"])
    income = st.number_input("Annual family income (₹)", min_value=0, max_value=100000000, value=150000, step=10000)
    category = st.selectbox("Social category", ["Any","General","OBC","SC","ST","EWS"])
    gender = st.selectbox("Gender", ["Any","Female","Male","Other"])
    search = st.text_input("Search schemes by keyword", placeholder="education, farmer, housing...")

try:
    schemes = load_schemes()
except (FileNotFoundError, pd.errors.ParserError, UnicodeDecodeError) as error:
    st.error(f"Could not load schemes.csv: {error}")
    st.stop()

if search.strip():
    term = search.strip().lower()
    schemes = schemes[schemes.apply(lambda r: term in " ".join(map(str, r.values)).lower(), axis=1)]

results = []
for _, row in schemes.iterrows():
    score, total, reasons, exact = profile_match(row, age, state, occupation, income, category, gender)
    results.append({"scheme":row["name"],"description":row["description"],"benefit":row["benefit"],
                    "score":score,"total":total,"reasons":reasons,"exact":exact,"state":row["state"],
                    "url":row["official_url"],"source_note":row["source_note"]})
results.sort(key=lambda x:(x["exact"],x["score"]), reverse=True)
c1,c2,c3 = st.columns(3)
c1.metric("Schemes in current results",len(results))
c2.metric("Potential matches",sum(x["exact"] for x in results))
c3.metric("Profile state",state)
st.info("Educational prototype: matches are simplified estimates, not official eligibility decisions. Verify current rules, documents and deadlines on official government portals.")
if not results:
    st.warning("No schemes matched your keyword. Try another search term.")
for item in results:
    label = "Potential match" if item["exact"] else f"Partial match ({item['score']}/{item['total']} rules)"
    with st.expander(f"{'✅' if item['exact'] else '🔎'} {item['scheme']} — {label}", expanded=item["exact"]):
        st.write(item["description"])
        st.markdown(f"**Listed benefit:** {item['benefit']}")
        if item["reasons"]:
            st.markdown("**Why it appeared:**")
            for reason in item["reasons"]:
                st.write(f"- {reason}")
        st.markdown(f"**Coverage:** {item['state']}")
        if item["source_note"]:
            st.caption(f"Source note: {item['source_note']}")
        url = str(item["url"]).strip()
        if url.startswith(("https://","http://")):
            st.link_button("Check official information",url)
        st.caption("Verify eligibility on the official source. Do not share Aadhaar numbers or bank details.")
st.divider()
st.markdown("### About SchemeSaathi")
st.write("A student prototype for exploring a sample catalogue of government schemes using profile-based filtering.")
st.caption("Built with Streamlit, pandas and SQLite • CSE 5th-semester project prototype")
