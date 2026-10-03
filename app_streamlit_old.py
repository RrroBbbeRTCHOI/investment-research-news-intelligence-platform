import streamlit as st
import pandas as pd


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Investment Research Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# SESSION STATE
# =========================================================

if "mode" not in st.session_state:
    st.session_state.mode = "Research"

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "AAPL"


# =========================================================
# GLOBAL CSS
# =========================================================

st.markdown(
    """
    <style>

    /* ================================================== */
    /* BASE                                               */
    /* ================================================== */

    html, body, [class*="css"] {
        font-family:
            Inter,
            ui-sans-serif,
            system-ui,
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;
    }

    .stApp {
        background: #080D16;
        color: #F1F5F9;
    }

    .block-container {
        max-width: 1540px;
        padding-top: 0.8rem;
        padding-bottom: 3rem;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        background: transparent !important;
    }


    /* ================================================== */
    /* TYPOGRAPHY                                         */
    /* ================================================== */

    h1, h2, h3, h4, h5, h6 {
        color: #F1F5F9 !important;
    }

    p {
        color: #8B9AAF;
    }

    .muted {
        color: #56657A;
    }

    .secondary {
        color: #8B9AAF;
    }

    .eyebrow {
        font-size: 0.70rem;
        color: #56657A;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        font-weight: 700;
    }

    .page-title {
        font-size: 1.20rem;
        font-weight: 700;
        color: #F1F5F9;
        margin-top: 3px;
    }

    .page-subtitle {
        font-size: 0.78rem;
        color: #6F7F95;
        margin-top: 2px;
    }


    /* ================================================== */
    /* TOP NAV                                            */
    /* ================================================== */

    .brand-name {
        font-size: 1.02rem;
        font-weight: 750;
        color: #F1F5F9;
        letter-spacing: 0.01em;
        line-height: 1.2;
    }

    .brand-subtitle {
        font-size: 0.68rem;
        color: #56657A;
        margin-top: 4px;
        letter-spacing: 0.03em;
    }

    .top-rule {
        height: 1px;
        background: #162235;
        margin-top: 12px;
        margin-bottom: 22px;
    }


    /* ================================================== */
    /* BUTTONS                                            */
    /* ================================================== */

    .stButton > button {
        background: #0D1523;
        color: #8B9AAF;
        border: 1px solid #1B2A40;
        border-radius: 7px;
        font-size: 0.80rem;
        font-weight: 650;
        min-height: 38px;
        transition: all 0.15s ease;
    }

    .stButton > button:hover {
        border-color: #4C8DFF;
        color: #F1F5F9;
        background: #101B2D;
    }

    .stButton > button:focus {
        box-shadow: none;
    }


    /* ================================================== */
    /* INPUTS                                             */
    /* ================================================== */

    div[data-baseweb="select"] > div {
        background: #0D1523;
        border: 1px solid #1B2A40;
        color: #E2E8F0;
        border-radius: 7px;
        min-height: 40px;
    }

    input {
        background: #0D1523 !important;
        color: #E2E8F0 !important;
        border: 1px solid #1B2A40 !important;
        border-radius: 7px !important;
    }

    label[data-testid="stWidgetLabel"] p {
        font-size: 0.69rem !important;
        color: #75869B !important;
        font-weight: 650 !important;
    }


    /* ================================================== */
    /* METRICS                                            */
    /* ================================================== */

    div[data-testid="stMetric"] {
        background: #0D1523;
        border: 1px solid #18263A;
        border-radius: 9px;
        padding: 14px 15px;
    }

    div[data-testid="stMetricLabel"] {
        color: #75869B;
        font-size: 0.72rem;
    }

    div[data-testid="stMetricValue"] {
        color: #F1F5F9;
        font-size: 1.30rem;
        font-weight: 700;
    }


    /* ================================================== */
    /* CARD                                               */
    /* ================================================== */

    .panel {
        background: #0D1523;
        border: 1px solid #18263A;
        border-radius: 10px;
        padding: 17px 18px;
    }

    .panel-title {
        color: #DDE6F1;
        font-weight: 700;
        font-size: 0.86rem;
    }

    .panel-caption {
        color: #607188;
        font-size: 0.72rem;
        margin-top: 3px;
    }


    /* ================================================== */
    /* SCREENER FILTER BAR                                */
    /* ================================================== */

    .filter-label {
        font-size: 0.69rem;
        font-weight: 700;
        color: #6F7F95;
        letter-spacing: 0.02em;
        margin-bottom: 5px;
    }


    /* ================================================== */
    /* CUSTOM TABLE                                       */
    /* ================================================== */

    .research-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        background: #0B1320;
        border: 1px solid #18263A;
        border-radius: 10px;
        overflow: hidden;
        font-size: 0.79rem;
    }

    .research-table thead th {
        text-align: left;
        padding: 12px 12px;
        color: #677A91;
        font-size: 0.67rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.055em;
        background: #0E1726;
        border-bottom: 1px solid #1B2A40;
        white-space: nowrap;
    }

    .research-table tbody td {
        padding: 13px 12px;
        color: #C8D2DF;
        border-bottom: 1px solid #142033;
    }

    .research-table tbody tr:last-child td {
        border-bottom: none;
    }

    .research-table tbody tr:hover td {
        background: #101B2D;
    }

    .ticker {
        color: #FFFFFF !important;
        font-weight: 750;
    }

    .positive {
        color: #2DD4A8 !important;
        font-weight: 650;
    }

    .negative {
        color: #FF5C6C !important;
        font-weight: 650;
    }

    .neutral {
        color: #F5B942 !important;
        font-weight: 650;
    }

    .rating-buy {
        display: inline-block;
        color: #2DD4A8;
        border: 1px solid rgba(45, 212, 168, 0.35);
        background: rgba(45, 212, 168, 0.08);
        border-radius: 5px;
        padding: 3px 7px;
        font-weight: 750;
        font-size: 0.68rem;
    }

    .rating-hold {
        display: inline-block;
        color: #F5B942;
        border: 1px solid rgba(245, 185, 66, 0.35);
        background: rgba(245, 185, 66, 0.08);
        border-radius: 5px;
        padding: 3px 7px;
        font-weight: 750;
        font-size: 0.68rem;
    }

    .rating-sell {
        display: inline-block;
        color: #FF5C6C;
        border: 1px solid rgba(255, 92, 108, 0.35);
        background: rgba(255, 92, 108, 0.08);
        border-radius: 5px;
        padding: 3px 7px;
        font-weight: 750;
        font-size: 0.68rem;
    }


    /* ================================================== */
    /* COMPANY HEADER                                     */
    /* ================================================== */

    .company-name {
        color: #F1F5F9;
        font-size: 1.62rem;
        font-weight: 760;
        line-height: 1.15;
    }

    .company-meta {
        color: #607188;
        font-size: 0.75rem;
        margin-top: 6px;
        letter-spacing: 0.03em;
    }

    .price {
        color: #F1F5F9;
        font-size: 1.42rem;
        font-weight: 750;
    }

    .price-change-negative {
        color: #FF5C6C;
        font-size: 0.75rem;
        font-weight: 700;
        margin-top: 4px;
    }

    .rating-large-sell {
        color: #FF5C6C;
        font-size: 1.05rem;
        font-weight: 800;
        letter-spacing: 0.05em;
    }

    .confidence {
        color: #6F7F95;
        font-size: 0.68rem;
        margin-top: 4px;
    }


    /* ================================================== */
    /* TABS                                               */
    /* ================================================== */

    button[data-baseweb="tab"] {
        color: #607188 !important;
        font-size: 0.78rem;
        font-weight: 650;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: #F1F5F9 !important;
    }

    div[data-baseweb="tab-highlight"] {
        background-color: #4C8DFF !important;
    }

    div[data-baseweb="tab-border"] {
        background-color: #18263A !important;
    }


    /* ================================================== */
    /* SECTION                                            */
    /* ================================================== */

    .section-header {
        font-size: 0.76rem;
        color: #8B9AAF;
        font-weight: 750;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 12px;
    }

    .section-rule {
        height: 1px;
        background: #162235;
        margin: 27px 0 25px 0;
    }


    /* ================================================== */
    /* NEWS                                               */
    /* ================================================== */

    .news-map {
        height: 575px;
        border: 1px solid #18263A;
        background:
            radial-gradient(
                circle at center,
                #11223A 0%,
                #0B1422 40%,
                #080D16 75%
            );
        border-radius: 12px;
        display: flex;
        justify-content: center;
        align-items: center;
        color: #607188;
    }

    .event-card {
        background: #0D1523;
        border: 1px solid #18263A;
        border-radius: 9px;
        padding: 15px;
        margin-bottom: 10px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# TOP NAVIGATION
# =========================================================

brand_col, nav_research, nav_news, search_col = st.columns(
    [5.5, 1.25, 1.6, 2.1],
    vertical_alignment="center"
)

with brand_col:
    st.markdown(
        """
        <div class="brand-name">
            Investment Research Platform
        </div>
        <div class="brand-subtitle">
            EQUITY RESEARCH & MARKET INTELLIGENCE
        </div>
        """,
        unsafe_allow_html=True
    )

with nav_research:
    if st.button(
        "RESEARCH",
        use_container_width=True
    ):
        st.session_state.mode = "Research"
        st.rerun()

with nav_news:
    if st.button(
        "NEWS INTELLIGENCE",
        use_container_width=True
    ):
        st.session_state.mode = "News"
        st.rerun()

with search_col:
    st.text_input(
        "Global Search",
        placeholder="Search ticker, company, event...",
        label_visibility="collapsed"
    )

st.markdown(
    '<div class="top-rule"></div>',
    unsafe_allow_html=True
)


# =========================================================
# RESEARCH MODE
# =========================================================

if st.session_state.mode == "Research":

    # -----------------------------------------------------
    # PAGE HEADER
    # -----------------------------------------------------

    left, right = st.columns([4, 1])

    with left:
        st.markdown(
            """
            <div class="eyebrow">
                Research Workspace
            </div>
            <div class="page-title">
                Equity Research
            </div>
            <div class="page-subtitle">
                Screening, fundamental analysis, valuation and investment research
            </div>
            """,
            unsafe_allow_html=True
        )

    with right:
        st.markdown(
            """
            <div style="text-align:right; padding-top:8px;">
                <span style="
                    color:#2DD4A8;
                    font-size:0.72rem;
                    font-weight:700;
                ">
                    ● MARKET OPEN
                </span>
                <div style="
                    color:#56657A;
                    font-size:0.68rem;
                    margin-top:3px;
                ">
                    US EQUITIES
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    st.write("")


    # =====================================================
    # SCREENER
    # =====================================================

    st.markdown(
        """
        <div class="section-header">
            Equity Screener
        </div>
        """,
        unsafe_allow_html=True
    )


    # -----------------------------------------------------
    # FILTER BAR
    # -----------------------------------------------------

    f1, f2, f3, f4, f5, f6, f7 = st.columns(
        [1.2, 1.1, 1.1, 1.0, 1.4, 1.4, 1.0]
    )

    with f1:
        min_growth = st.number_input(
            "Revenue Growth > %",
            value=0.0,
            step=1.0
        )

    with f2:
        min_roe = st.number_input(
            "ROE > %",
            value=0.0,
            step=1.0
        )

    with f3:
        min_roic = st.number_input(
            "ROIC > %",
            value=0.0,
            step=1.0
        )

    with f4:
        max_pe = st.number_input(
            "P/E <",
            value=100.0,
            step=1.0
        )

    with f5:
        sector = st.selectbox(
            "Sector",
            [
                "All Sectors",
                "Technology",
                "Communication Services",
                "Consumer",
                "Financials"
            ]
        )

    with f6:
        market_cap = st.selectbox(
            "Market Cap",
            [
                "All",
                "Mega Cap",
                "Large Cap",
                "Mid Cap"
            ]
        )

    with f7:
        st.write("")
        st.write("")
        st.button(
            "APPLY",
            use_container_width=True
        )


    st.write("")


    # -----------------------------------------------------
    # SCREENER TABLE
    # -----------------------------------------------------


    table_html = """
    <table class="research-table">
    <thead>
    <tr>
    <th>Ticker</th>
    <th>Company</th>
    <th>Revenue Growth</th>
    <th>ROE</th>
    <th>ROIC</th>
    <th>Operating Margin</th>
    <th>P/E</th>
    <th>Score</th>
    <th>Rating</th>
    </tr>
    </thead>

    <tbody>

    <tr>
    <td class="ticker">AAPL</td>
    <td>Apple Inc.</td>
    <td class="positive">+6.4%</td>
    <td>151.9%</td>
    <td>77.2%</td>
    <td>32.0%</td>
    <td>—</td>
    <td>67.7</td>
    <td><span class="rating-sell">SELL</span></td>
    </tr>

    <tr>
    <td class="ticker">MSFT</td>
    <td>Microsoft Corporation</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    </tr>

    <tr>
    <td class="ticker">NVDA</td>
    <td>NVIDIA Corporation</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    </tr>

    <tr>
    <td class="ticker">GOOGL</td>
    <td>Alphabet Inc.</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    </tr>

    <tr>
    <td class="ticker">AMZN</td>
    <td>Amazon.com Inc.</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    <td>—</td>
    </tr>

    </tbody>
    </table>
    """

    st.markdown(
        table_html,
        unsafe_allow_html=True
    )


    # =====================================================
    # COMPANY RESEARCH
    # =====================================================

    st.markdown(
        """
        <div class="section-header">
            Company Research
        </div>
        """,
        unsafe_allow_html=True
    )


    company_select_col, empty = st.columns([2.5, 5])

    with company_select_col:
        selected_company = st.selectbox(
            "Company",
            [
                "Apple Inc. (AAPL)",
                "Microsoft Corporation (MSFT)",
                "NVIDIA Corporation (NVDA)",
                "Alphabet Inc. (GOOGL)",
                "Amazon.com Inc. (AMZN)"
            ],
            label_visibility="collapsed"
        )


    company_data = {
        "Apple Inc. (AAPL)": {
            "name": "Apple Inc.",
            "ticker": "AAPL",
            "exchange": "NASDAQ",
            "price": "$314.58",
            "change": "-0.72%",
            "rating": "SELL",
            "confidence": "LOW CONFIDENCE",
            "revenue_growth": "6.43%",
            "roe": "151.91%",
            "roic": "77.18%",
            "operating_margin": "31.97%",
            "net_margin": "26.92%",
            "fundamental_score": "67.68",
            "research_score": "50.72",
            "earnings_quality": "88.24",
            "financial_health": "55.00",
            "non_core_score": "100.00",
            "non_core_contribution": "0.00%",
            "fair_value": "$175.23",
            "expected_return": "-44.30%"
        }
    }

    data = company_data.get(selected_company)

    if data:

        st.write("")

        c1, c2, c3 = st.columns(
            [4.3, 1.35, 1.35],
            vertical_alignment="center"
        )

        with c1:
            st.markdown(
                f"""
                <div class="company-name">
                    {data["name"]}
                </div>
                <div class="company-meta">
                    {data["ticker"]} &nbsp;&nbsp;•&nbsp;&nbsp;
                    {data["exchange"]}
                </div>
                """,
                unsafe_allow_html=True
            )

        with c2:
            st.markdown(
                f"""
                <div class="price">
                    {data["price"]}
                </div>
                <div class="price-change-negative">
                    {data["change"]}
                </div>
                """,
                unsafe_allow_html=True
            )

        with c3:
            st.markdown(
                f"""
                <div style="text-align:right;">
                    <div class="rating-large-sell">
                        {data["rating"]}
                    </div>
                    <div class="confidence">
                        {data["confidence"]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


        st.write("")


        # -------------------------------------------------
        # CORE METRICS
        # -------------------------------------------------

        m1, m2, m3, m4 = st.columns(4)

        with m1:
            st.metric(
                "Revenue Growth",
                data["revenue_growth"]
            )

        with m2:
            st.metric(
                "ROIC",
                data["roic"]
            )

        with m3:
            st.metric(
                "Operating Margin",
                data["operating_margin"]
            )

        with m4:
            st.metric(
                "P/E",
                "N/A"
            )


        st.write("")


        # -------------------------------------------------
        # RESEARCH TABS
        # -------------------------------------------------

        (
            overview_tab,
            financial_tab,
            valuation_tab,
            quality_tab,
            sec_tab,
            investment_tab
        ) = st.tabs(
            [
                "Overview",
                "Financials",
                "Valuation",
                "Earnings Quality",
                "SEC Filing",
                "Investment View"
            ]
        )


        # =================================================
        # OVERVIEW
        # =================================================

        with overview_tab:

            st.write("")

            o1, o2, o3 = st.columns(3)

            with o1:
                st.metric(
                    "Fundamental Score",
                    data["fundamental_score"]
                )

            with o2:
                st.metric(
                    "Research Score",
                    data["research_score"]
                )

            with o3:
                st.metric(
                    "Earnings Quality",
                    data["earnings_quality"]
                )


        # =================================================
        # FINANCIALS
        # =================================================

        with financial_tab:

            st.write("")

            f1, f2, f3 = st.columns(3)

            with f1:
                st.metric(
                    "Operating Margin",
                    data["operating_margin"]
                )

            with f2:
                st.metric(
                    "Net Margin",
                    data["net_margin"]
                )

            with f3:
                st.metric(
                    "Financial Health",
                    data["financial_health"]
                )


        # =================================================
        # VALUATION
        # =================================================

        with valuation_tab:

            st.write("")

            v1, v2, v3 = st.columns(3)

            with v1:
                st.metric(
                    "Current Price",
                    data["price"]
                )

            with v2:
                st.metric(
                    "Fair Value",
                    data["fair_value"]
                )

            with v3:
                st.metric(
                    "Expected Return",
                    data["expected_return"]
                )


        # =================================================
        # EARNINGS QUALITY
        # =================================================

        with quality_tab:

            st.write("")

            q1, q2, q3 = st.columns(3)

            with q1:
                st.metric(
                    "Earnings Quality",
                    data["earnings_quality"]
                )

            with q2:
                st.metric(
                    "Non-Core Score",
                    data["non_core_score"]
                )

            with q3:
                st.metric(
                    "Non-Core Contribution",
                    data["non_core_contribution"]
                )


        # =================================================
        # SEC
        # =================================================

        with sec_tab:

            st.write("")

            st.markdown(
                """
                <div class="panel">
                    <div class="panel-title">
                        SEC Filing Intelligence
                    </div>

                    <div class="panel-caption">
                        10-K / 10-Q parsing, earnings composition,
                        non-operating income and risk-factor review
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


        # =================================================
        # INVESTMENT VIEW
        # =================================================

        with investment_tab:

            st.write("")

            i1, i2, i3, i4 = st.columns(4)

            with i1:
                st.metric(
                    "Current Price",
                    data["price"]
                )

            with i2:
                st.metric(
                    "Fair Value",
                    data["fair_value"]
                )

            with i3:
                st.metric(
                    "Expected Return",
                    data["expected_return"]
                )

            with i4:
                st.metric(
                    "Confidence",
                    "Low"
                )

            st.write("")

            st.error(
                "Current market price implies very aggressive "
                "future FCFF growth assumptions."
            )

    else:

        st.info(
            "Research data for this company has not been loaded yet."
        )


# =========================================================
# NEWS MODE
# =========================================================

else:

    # -----------------------------------------------------
    # PAGE HEADER
    # -----------------------------------------------------

    st.markdown(
        """
        <div class="eyebrow">
            Intelligence Workspace
        </div>

        <div class="page-title">
            Global News Intelligence
        </div>

        <div class="page-subtitle">
            Geographic event monitoring, market impact
            and watchlist relevance
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("")


    # -----------------------------------------------------
    # FILTERS
    # -----------------------------------------------------

    n1, n2, n3 = st.columns(
        [1.6, 1.6, 4]
    )

    with n1:
        st.selectbox(
            "Region",
            [
                "Global",
                "United States",
                "China",
                "Europe",
                "Middle East",
                "Asia Pacific"
            ]
        )

    with n2:
        st.selectbox(
            "Time Window",
            [
                "Last 1 Hour",
                "Last 6 Hours",
                "Last 24 Hours",
                "Last 7 Days"
            ]
        )

    with n3:
        st.text_input(
            "Event Search",
            placeholder="Search event, sector, company, country..."
        )


    st.write("")


    # -----------------------------------------------------
    # MAP + EVENTS
    # -----------------------------------------------------

    map_col, events_col = st.columns(
        [4.7, 1.5]
    )

    with map_col:

        st.markdown(
            """
            <div class="news-map">

                <div style="text-align:center;">

                    <div style="
                        font-size:2.1rem;
                        margin-bottom:10px;
                    ">
                        🌍
                    </div>

                    <div style="
                        color:#8B9AAF;
                        font-size:0.88rem;
                        font-weight:650;
                    ">
                        Global Event Map
                    </div>

                    <div style="
                        color:#56657A;
                        font-size:0.72rem;
                        margin-top:6px;
                    ">
                        Interactive globe layer will be inserted here
                    </div>

                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

    with events_col:

        st.markdown(
            """
            <div class="section-header">
                Live Events
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <div class="event-card">

                <div style="
                    color:#FF5C6C;
                    font-size:0.68rem;
                    font-weight:800;
                    letter-spacing:0.08em;
                ">
                    ● WITHIN 1 HOUR
                </div>

                <div style="
                    margin-top:8px;
                    color:#DDE6F1;
                    font-weight:700;
                    font-size:0.82rem;
                ">
                    Breaking Global Event
                </div>

                <div style="
                    margin-top:6px;
                    color:#607188;
                    font-size:0.72rem;
                    line-height:1.45;
                ">
                    Watchlist relevance and affected tickers
                    will appear here.
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            """
            <div class="event-card">

                <div style="
                    color:#F5B942;
                    font-size:0.68rem;
                    font-weight:800;
                    letter-spacing:0.08em;
                ">
                    ● WITHIN 6 HOURS
                </div>

                <div style="
                    margin-top:8px;
                    color:#DDE6F1;
                    font-weight:700;
                    font-size:0.82rem;
                ">
                    Recent Market Event
                </div>

                <div style="
                    margin-top:6px;
                    color:#607188;
                    font-size:0.72rem;
                    line-height:1.45;
                ">
                    Relevance score, sectors and ticker
                    exposure will appear here.
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )