import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="SchemeSaathi",
    page_icon="🇮🇳",
    layout="wide"
)

DATA_PATH = Path(__file__).parent / "schemes.csv"


@st.cache_data
def load_schemes():
    return pd.read_csv(DATA_PATH).fillna("")


def profile_match(
    row, age, state, occupation,
    annual_income, category, gender
):
    reasons = []

    checks = [
        (
            "min_age",
            age >= int(row["min_age"]),
            f"Minimum age: {int(row['min_age'])}"
        ),
        (
            "max_age",
            age <= int(row["max_age"]),
            f"Maximum age: {int(row['max_age'])}"
        ),
        (
            "state",
            row["state"] == "All India"
            or row["state"] == state,
            "State matches"
            if row["state"] == "All India"
            else f"Available in {row['state']}"
        ),
        (
            "occupation",
            row["occupation"] == "Any"
            or row["occupation"] == occupation,
            "Occupation matches"
            if row["occupation"] == "Any"
            else f"For {row['occupation']}"
        ),
        (
            "category",
            row["category"] == "Any"
            or row["category"] == category,
            "Category matches"
            if row["category"] == "Any"
            else f"Category: {row['category']}"
        ),
        (
            "gender",
            row["gender"] == "Any"
            or row["gender"] == gender,
            "Gender matches"
            if row["gender"] == "Any"
            else f"For {row['gender']} applicants"
        ),
    ]

    # Safely handle the scheme's income limit
    income_limit = str(row.get("max_income", "")).strip()

    if income_limit.lower() in ("", "none", "nan", "null"):
        income_ok = True
        income_limit_display = "No limit listed"
    else:
        try:
            income_limit_value = float(income_limit)

            income_ok = (
                annual_income <= income_limit_value
            )

            income_limit_display = (
                f"₹{income_limit_value:,.0f}"
            )

        except (ValueError, TypeError):
            income_ok = False
            income_limit_display = "Invalid income limit"

    checks.append((
        "income",
        income_ok,
        "Income within listed limit"
        if income_ok
        else f"Listed income limit: {income_limit_display}"
    ))

    passed = sum(
        1 for _, ok, _ in checks if ok
    )

    for _, ok, reason in checks:
        if ok:
            reasons.append(reason)

    return (
        passed,
        len(checks),
        reasons,
        all(ok for _, ok, _ in checks)
    )


st.title("🇮🇳 SchemeSaathi")

st.subheader(
    "Find government schemes that may fit your profile"
)

st.caption(
    "Student project prototype • Always verify eligibility "
    "and deadlines on the official scheme website."
)


with st.sidebar:
    st.header("Your profile")

    age = st.slider(
        "Age", 1, 100, 21
    )

    state = st.selectbox(
        "State / UT",
        [
            "Karnataka",
            "Maharashtra",
            "Telangana",
            "Andhra Pradesh",
            "Tamil Nadu",
            "Kerala",
            "Goa",
            "Delhi",
            "Uttar Pradesh",
            "Other"
        ]
    )

    occupation = st.selectbox(
        "Occupation",
        [
            "Student",
            "Farmer",
            "Worker",
            "Entrepreneur",
            "Unemployed",
            "Other"
        ]
    )

    annual_income = st.number_input(
        "Annual family income (₹)",
        min_value=0,
        max_value=100000000,
        value=150000,
        step=10000
    )

    category = st.selectbox(
        "Social category",
        ["Any", "General", "OBC", "SC", "ST", "EWS"]
    )

    gender = st.selectbox(
        "Gender",
        ["Any", "Female", "Male", "Other"]
    )

    search = st.text_input(
        "Search schemes by keyword",
        placeholder="education, farmer, housing..."
    )


# Load scheme data
try:
    schemes = load_schemes()
except (FileNotFoundError, pd.errors.ParserError) as error:
    st.error(
        f"Could not load schemes.csv: {error}"
    )
    st.stop()


# Validate required CSV columns
required_columns = {
    "name",
    "description",
    "benefit",
    "min_age",
    "max_age",
    "state",
    "occupation",
    "category",
    "gender",
    "max_income",
    "official_url",
    "source_note"
}

missing_columns = required_columns - set(schemes.columns)

if missing_columns:
    st.error(
        "Missing columns in schemes.csv: "
        + ", ".join(sorted(missing_columns))
    )
    st.stop()


# Keyword search
if search.strip():
    mask = schemes.apply(
        lambda r: search.lower()
        in " ".join(map(str, r.values)).lower(),
        axis=1
    )

    schemes = schemes[mask]


# Match schemes to the user's profile
results = []

for _, row in schemes.iterrows():
    try:
        score, total, reasons, exact = profile_match(
            row,
            age,
            state,
            occupation,
            annual_income,
            category,
            gender
        )

        results.append({
            "scheme": row["name"],
            "description": row["description"],
            "benefit": row["benefit"],
            "score": score,
            "total": total,
            "reasons": reasons,
            "exact": exact,
            "state": row["state"],
            "url": row["official_url"],
            "source_note": row["source_note"]
        })

    except (ValueError, TypeError, KeyError) as error:
        st.warning(
            f"Could not process scheme '{row.get('name', 'Unknown')}': "
            f"{error}"
        )


# Sort potential matches first
results.sort(
    key=lambda x: (x["exact"], x["score"]),
    reverse=True
)

eligible = sum(
    1 for r in results if r["exact"]
)


# Dashboard metrics
col1, col2, col3 = st.columns(3)

col1.metric(
    "Schemes in current results",
    len(results)
)

col2.metric(
    "Potential matches",
    eligible
)

col3.metric(
    "Profile state",
    state
)


st.info(
    "Prototype notice: This demo uses a small sample dataset "
    "and simplified rules. A match is not an official government "
    "eligibility decision. Check current rules, required documents, "
    "application dates, and official portals before applying."
)


# Display matching schemes
if not results:
    st.warning(
        "No schemes matched your keyword. "
        "Try another search term."
    )

else:
    for item in results:

        label = (
            "Potential match"
            if item["exact"]
            else f"Partial match ({item['score']}/{item['total']} rules)"
        )

        icon = "✅" if item["exact"] else "🔎"

        with st.expander(
            f"{icon} {item['scheme']} — {label}",
            expanded=item["exact"]
        ):

            st.write(item["description"])

            st.markdown(
                f"**Listed benefit:** {item['benefit']}"
            )

            if item["reasons"]:
                st.markdown("**Why it appeared:**")

                for reason in item["reasons"]:
                    st.write(f"- {reason}")

            st.markdown(
                f"**Coverage:** {item['state']}"
            )

            st.markdown(
                f"**Source note:** {item['source_note']}"
            )

            url = str(item["url"]).strip()

            if url.startswith(("https://", "http://")):
                st.link_button(
                    "Check official information",
                    url
                )

            st.caption(
                "Verify the latest eligibility criteria on the "
                "official source. Do not share Aadhaar numbers, "
                "bank details, or other sensitive information "
                "in this prototype."
            )


st.divider()

st.markdown("### Project features to extend")

st.write(
    "• Add verified scheme records and update dates\n"
    "• Kannada/English interface\n"
    "• Document checklist\n"
    "• Saved searches\n"
    "• Admin panel for dataset review"
)

st.caption(
    "Built with Streamlit + pandas. "
    "This app does not submit applications or guarantee benefits."
)