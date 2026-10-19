import streamlit as st
import plotly.graph_objects as go
from streamlit_option_menu import option_menu
from dbhelper import DB

# ---------- Page setup ----------
st.set_page_config(page_title="Flight Analytics", page_icon="✈️", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 12px;
        padding: 16px;
        min-height: 140px;
    }
    #MainMenu, footer {visibility: hidden;}
    .block-container {padding-top: 2rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# One DB object for the whole session (not recreated on every rerun)
@st.cache_resource
def get_db():
    return DB()

db = get_db()

# Cache query results so the app stays fast
@st.cache_data
def cities():
    return sorted(db.fetch_city_name())

@st.cache_data
def airline_freq():
    return db.fetch_airline_frequency()

@st.cache_data
def busiest():
    return db.busiest_airport()


@st.cache_data
def airline_names():
    return sorted(airline_freq()[0])

@st.cache_data
def class_names():
    return db.fetch_classes()

@st.cache_data
def get_destinations_from(source):
    return sorted(db.fetch_destinations_from(source))


@st.cache_data
def source_cities():
    return sorted(db.fetch_source_cities())

@st.cache_data
def destination_cities():
    return sorted(db.fetch_destination_cities())

@st.cache_data
def get_kpis(airline, flight_class, destination):
    return db.kpis(airline, flight_class, destination)

@st.cache_data
def get_airline_prices(flight_class, destination):
    return db.avg_price_by_airline(flight_class, destination)

@st.cache_data
def get_price_curve(airline, flight_class, destination):
    return db.price_by_days_left(airline, flight_class, destination)


@st.cache_data
def get_route_flights(source, destination):
    return db.fetch_all_flight(source, destination)


@st.cache_data
def get_analytics_data():
    return db.analytics_data()


def avg_fare_by(d, by):
    """Average fare per group, weighted correctly from the aggregated table."""
    g = d.groupby(by, as_index=False)[["flights", "total_price"]].sum()
    g["avg_fare"] = (g["total_price"] / g["flights"]).round()
    return g


def style_fig(fig, title, height=380, y_title="Avg fare (₹)"):
    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor="left"),
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=60, b=20, l=20, r=20), yaxis_title=y_title,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )
    return fig


def show(container, fig):
    with container:
        with st.container(border=True):
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ---------- Reusable donut chart ----------
PALETTE = ["#00C2FF", "#6366F1", "#10B981", "#F59E0B", "#EF4444", "#A855F7"]

def donut(labels, values, title, center_label="Total flights"):
    total = sum(values)
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.65,
            sort=False,
            marker=dict(colors=PALETTE, line=dict(color="rgba(0,0,0,0)", width=3)),
            textinfo="percent",
            textposition="inside",
            hovertemplate="<b>%{label}</b><br>Flights: %{value:,.0f}<br>Share: %{percent}<extra></extra>",
        )
    )
    fig.add_annotation(
        text=f"<b>{total:,.0f}</b><br><sup>{center_label}</sup>",
        x=0.5, y=0.5, showarrow=False, font=dict(size=20),
    )
    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor="left"),
        height=430,
        margin=dict(t=70, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
    )
    return fig


# ---------- Sidebar menu ----------
with st.sidebar:
    page = option_menu(
        "Flight Analytics",
        ["Overview", "Check Flight", "Analytics", "About"],
        icons=["house", "search", "bar-chart", "info-circle"],
        default_index=0,
    )

# ---------- Pages ----------
if page == "Overview":
    st.title("Flight overview")
    st.caption("Filters apply to every card and chart on this page.")

    f1, f2, f3 = st.columns(3)
    airline = f1.selectbox("Airline", ["All"] + airline_names())
    flight_class = f2.selectbox("Class", ["All"] + class_names())
    destination = f3.selectbox("Destination", ["All"] + destination_cities())

    k = get_kpis(airline, flight_class, destination)
    base = get_kpis("All", "All", "All")

    if k["total_flights"] == 0:
        st.warning("No flights match these filters. Try changing one of them.")
        st.stop()

    fare_diff = k["avg_price"] - base["avg_price"]
    dur_diff = k["avg_duration"] - base["avg_duration"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "Total flights", f"{k['total_flights']:,}",
        delta=f"{k['total_flights'] / base['total_flights']:.0%} of all flights",
        delta_color="off",
    )
    c2.metric(
        "Average fare", f"₹{k['avg_price']:,.0f}",
        delta=f"{fare_diff:+,.0f} vs overall" if fare_diff else None,
        delta_color="inverse",  # higher fare = red
    )
    c3.metric("Cheapest fare", f"₹{k['min_price']:,.0f}")
    c4.metric(
        "Average duration", f"{k['avg_duration']} hrs",
        delta=f"{dur_diff:+.1f} hrs vs overall" if dur_diff else None,
        delta_color="inverse",
    )
    c5.metric("Top destination", k["top_destination"])

    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            df = get_airline_prices(flight_class, destination)
            fig = go.Figure(go.Bar(
                x=df["airline"], y=df["avg_price"],
                marker_color=["#00C2FF" if a == airline else "#94A3B8" for a in df["airline"]]
                if airline != "All" else "#00C2FF",
                hovertemplate="<b>%{x}</b><br>Avg fare: ₹%{y:,.0f}<extra></extra>",
            ))
            fig.update_layout(
                title="Average fare by airline",
                height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=60, b=20, l=20, r=20), yaxis_title="Fare (₹)",
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with right:
        with st.container(border=True):
            df = get_price_curve(airline, flight_class, destination)
            fig = go.Figure(go.Scatter(
                x=df["days_left"], y=df["avg_price"],
                mode="lines", line=dict(color="#F59E0B", width=3),
                hovertemplate="%{x} days before<br>Avg fare: ₹%{y:,.0f}<extra></extra>",
            ))
            fig.update_layout(
                title="Fare vs days before departure",
                height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=60, b=20, l=20, r=20),
                xaxis_title="Days left", yaxis_title="Avg fare (₹)",
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

elif page == "Check Flight":
    st.title("Check flights")

    c1, c2 = st.columns(2)
    sources = source_cities()
    source = c1.selectbox("From", sources, index=sources.index("Delhi") if "Delhi" in sources else 0)

    # "To" only lists cities that really have flights from the chosen "From"
    dest_options = get_destinations_from(source)
    if not dest_options:
        st.warning("No destinations found for this city.")
        st.stop()
    destination = c2.selectbox(
        "To", dest_options, index=dest_options.index("Mumbai") if "Mumbai" in dest_options else 0
    )

    df = get_route_flights(source, destination).copy()
    if df.empty:
        st.warning("No flights found for this route.")
        st.stop()

    # Make raw values readable
    stop_labels = {"zero": "Non-stop", "one": "1 stop", "two_or_more": "2+ stops"}
    df["stops"] = df["stops"].map(stop_labels).fillna(df["stops"])
    for col in ("departure_time", "arrival_time"):
        df[col] = df[col].str.replace("_", " ")

    # ---- Filters ----
    f1, f2, f3, f4 = st.columns(4)
    classes = sorted(df["class"].unique())
    airlines = sorted(df["airline"].unique())
    stops_all = sorted(df["stops"].unique())
    times_all = list(df["departure_time"].unique())

    sel_class = f1.multiselect("Class", classes, default=classes)
    sel_airline = f2.multiselect("Airline", airlines, default=airlines)
    sel_stops = f3.multiselect("Stops", stops_all, default=stops_all)
    sel_time = f4.multiselect("Departure time", times_all, default=times_all)

    base = df[
        df["class"].isin(sel_class)
        & df["airline"].isin(sel_airline)
        & df["stops"].isin(sel_stops)
        & df["departure_time"].isin(sel_time)
    ]
    if base.empty:
        st.warning("No flights match these filters. Try widening them.")
        st.stop()

    # Fare slider adapts to the flights left after the filters above.
    # (Economy and Business fares differ a lot, so one fixed range doesn't fit both.)
    p_min, p_max = int(base["price"].min()), int(base["price"].max())
    step = 100 if (p_max - p_min) < 10000 else 500
    lo = (p_min // step) * step
    hi = -(-p_max // step) * step
    price_range = (lo, hi)
    if lo < hi:
        price_range = st.slider(
            "Fare range (₹)", lo, hi, (lo, hi), step=step,
            format="₹%d", key=f"fare_{lo}_{hi}",  # key resets the slider when its bounds change
        )
    st.caption(f"Median fare for these filters: ₹{base['price'].median():,.0f}")

    res = base[base["price"].between(*price_range)]

    if res.empty:
        st.warning("No flights match these filters. Try widening them.")
        st.stop()

    # ---- Summary cards ----
    cheapest = res.loc[res["price"].idxmin()]
    fastest = res.loc[res["duration"].idxmin()]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Flights found", f"{len(res):,}")
    m2.metric("Cheapest fare", f"₹{cheapest['price']:,.0f}", delta=cheapest["airline"], delta_color="off")
    m3.metric("Average fare", f"₹{res['price'].mean():,.0f}")
    m4.metric("Fastest flight", f"{fastest['duration']:.1f} hrs", delta=fastest["airline"], delta_color="off")

    st.success(
        f"💡 Best deal: **{cheapest['airline']}** {cheapest['flight']}, "
        f"{cheapest['stops']}, departs {cheapest['departure_time']} — "
        f"**₹{cheapest['price']:,.0f}** ({cheapest['class']})"
    )

    # ---- Table + chart ----
    tab1, tab2 = st.tabs(["📋 Flights", "📈 Price vs duration"])

    with tab1:
        sort_by = st.selectbox(
            "Sort by", ["Price (low to high)", "Price (high to low)", "Duration (shortest)"]
        )
        if sort_by == "Price (low to high)":
            table = res.sort_values("price")
        elif sort_by == "Price (high to low)":
            table = res.sort_values("price", ascending=False)
        else:
            table = res.sort_values("duration")

        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_order=["airline", "flight", "departure_time", "arrival_time",
                          "stops", "class", "duration", "days_left", "price"],
            column_config={
                "airline": "Airline",
                "flight": "Flight",
                "departure_time": "Departs",
                "arrival_time": "Arrives",
                "stops": "Stops",
                "class": "Class",
                "duration": st.column_config.NumberColumn("Duration", format="%.1f hrs"),
                "days_left": st.column_config.NumberColumn("Days left", format="%d"),
                "price": st.column_config.NumberColumn("Fare", format="₹%d"),
            },
        )
        st.download_button(
            "⬇ Download results (CSV)",
            table.to_csv(index=False).encode("utf-8"),
            file_name=f"{source}_to_{destination}_flights.csv",
            mime="text/csv",
        )

    with tab2:
        fig = go.Figure()
        for i, (name, g) in enumerate(res.groupby("airline")):
            fig.add_trace(go.Scatter(
                x=g["duration"], y=g["price"], mode="markers", name=name,
                marker=dict(size=8, opacity=0.75, color=PALETTE[i % len(PALETTE)]),
                customdata=g[["flight", "stops", "class"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b> (%{customdata[2]})<br>"
                    "%{customdata[1]}<br>%{x:.1f} hrs · ₹%{y:,.0f}<extra></extra>"
                ),
            ))
        fig.update_layout(
            height=420,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=30, b=20, l=20, r=20),
            xaxis_title="Duration (hrs)", yaxis_title="Fare (₹)",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

elif page == "Analytics":
    st.title("Flight analytics")

    TIME_ORDER = ["Early Morning", "Morning", "Afternoon", "Evening", "Night", "Late Night"]
    STOP_ORDER = ["Non-stop", "1 stop", "2+ stops"]
    CLASS_COLORS = {"Economy": "#00C2FF", "Business": "#F59E0B"}

    raw = get_analytics_data().copy()
    raw["stops"] = raw["stops"].map(
        {"zero": "Non-stop", "one": "1 stop", "two_or_more": "2+ stops"}
    ).fillna(raw["stops"])
    raw["departure_time"] = raw["departure_time"].str.replace("_", " ")

    # ---- Filters ----
    classes = sorted(raw["class"].unique())
    airlines = sorted(raw["airline"].unique())
    dests = sorted(raw["destination_city"].unique())
    f1, f2, f3 = st.columns(3)
    sel_class = f1.multiselect("Class", classes, default=["Economy"] if "Economy" in classes else classes)
    sel_airline = f2.multiselect("Airline", airlines, default=airlines)
    sel_dest = f3.multiselect("Destination", dests, default=dests)

    data = raw[
        raw["class"].isin(sel_class)
        & raw["airline"].isin(sel_airline)
        & raw["destination_city"].isin(sel_dest)
    ]
    if data.empty:
        st.warning("No data for these filters. Try widening them.")
        st.stop()
    if len(sel_class) > 1:
        st.caption("Tip: Business fares are much higher, so mixing classes skews averages. Pick one class for fair comparisons.")

    # ---- KPI cards ----
    total = int(data["flights"].sum())
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Flights analysed", f"{total:,}")
    k2.metric("Average fare", f"₹{data['total_price'].sum() / total:,.0f}")
    k3.metric("Average duration", f"{data['total_duration'].sum() / total:.1f} hrs")
    k4.metric("Non-stop share", f"{data.loc[data['stops'] == 'Non-stop', 'flights'].sum() / total:.0%}")

    # ---- Auto insights ----
    by_time = avg_fare_by(data, "departure_time")
    by_air = avg_fare_by(data, "airline")
    by_stop = avg_fare_by(data, "stops").set_index("stops")
    t_best = by_time.loc[by_time["avg_fare"].idxmin()]
    a_low = by_air.loc[by_air["avg_fare"].idxmin()]
    a_high = by_air.loc[by_air["avg_fare"].idxmax()]
    insights = [
        f"💡 Cheapest departure time: **{t_best['departure_time']}** (avg ₹{t_best['avg_fare']:,.0f})",
        f"💡 Lowest average fare: **{a_low['airline']}** (₹{a_low['avg_fare']:,.0f}) · "
        f"Highest: **{a_high['airline']}** (₹{a_high['avg_fare']:,.0f})",
    ]
    if "Non-stop" in by_stop.index and "1 stop" in by_stop.index:
        diff = by_stop.loc["1 stop", "avg_fare"] - by_stop.loc["Non-stop", "avg_fare"]
        word = "more" if diff > 0 else "less"
        insights.append(f"💡 1-stop flights cost on average **₹{abs(diff):,.0f} {word}** than non-stop")
    st.info("\n\n".join(insights))

    def grouped_bar(x, order, title):
        fig = go.Figure()
        for cls, g in data.groupby("class"):
            t = avg_fare_by(g, x).set_index(x).reindex(order).reset_index()
            fig.add_trace(go.Bar(
                name=cls, x=t[x], y=t["avg_fare"], marker_color=CLASS_COLORS.get(cls),
                hovertemplate="<b>%{x}</b><br>" + cls + ": ₹%{y:,.0f}<extra></extra>",
            ))
        fig.update_layout(barmode="group")
        return style_fig(fig, title)

    tab1, tab2, tab3 = st.tabs(["✈️ Airlines", "🗺️ Routes", "⏰ Timing & stops"])

    with tab1:
        a, b = st.columns(2)
        fa = data.groupby("airline", as_index=False)["flights"].sum()
        show(a, donut(fa["airline"], fa["flights"], "Flights by airline"))
        show(b, grouped_bar("airline", sorted(data["airline"].unique()), "Average fare by airline"))

    with tab2:
        a, b = st.columns(2)
        by_dest = avg_fare_by(data, "destination_city").sort_values("avg_fare", ascending=False)
        fig = go.Figure(go.Bar(
            x=by_dest["destination_city"], y=by_dest["avg_fare"], marker_color="#6366F1",
            hovertemplate="<b>%{x}</b><br>Avg fare: ₹%{y:,.0f}<extra></extra>",
        ))
        show(a, style_fig(fig, "Average fare by destination"))
        fd = data.groupby("destination_city", as_index=False)["flights"].sum()
        show(b, donut(fd["destination_city"], fd["flights"], "Flights by destination"))

    with tab3:
        a, b = st.columns(2)
        times = [t for t in TIME_ORDER if t in set(data["departure_time"])]
        stops = [s for s in STOP_ORDER if s in set(data["stops"])]
        show(a, grouped_bar("departure_time", times, "Average fare by departure time"))
        show(b, grouped_bar("stops", stops, "Average fare by number of stops"))

        hm = avg_fare_by(data, ["destination_city", "departure_time"]).pivot(
            index="destination_city", columns="departure_time", values="avg_fare"
        ).reindex(columns=times)
        fig = go.Figure(go.Heatmap(
            z=hm.values, x=hm.columns, y=hm.index, colorscale="Blues",
            texttemplate="₹%{z:,.0f}", colorbar=dict(title="₹"),
            hovertemplate="%{y} · %{x}<br>Avg fare: ₹%{z:,.0f}<extra></extra>",
        ))
        show(st.container(), style_fig(fig, "Average fare: destination × departure time", y_title=""))

elif page == "About":
    st.title("About this project")
    st.caption("Flight Analytics: an interactive dashboard for exploring flight fares.")

    k = get_kpis("All", "All", "All")
    sources, dests = source_cities(), destination_cities()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Flights in dataset", f"{k['total_flights']:,}")
    m2.metric("Airlines", len(airline_names()))
    m3.metric("Destinations", len(dests))
    m4.metric("Average fare", f"₹{k['avg_price']:,.0f}")

    with st.container(border=True):
        st.subheader("🎯 What is this project?")
        st.write(
            "This dashboard helps you explore flight fares and answer practical questions: "
            "Which airline is cheapest? When is the best time to fly? How much does booking early "
            "save? How do Economy and Business fares compare? It combines a MySQL database, "
            "Python, and interactive charts in one web app."
        )
        st.write(
            f"**Dataset:** a Kaggle flight price dataset stored in a MySQL table named `flight`. "
            f"It currently holds flights from **{', '.join(sources)}** to **{', '.join(dests)}**. "
            "Each record has the airline, flight number, departure and arrival time, stops, class, "
            "duration, days left before departure, and price."
        )

    st.subheader("✨ Pages")
    p1, p2, p3 = st.columns(3)
    with p1:
        with st.container(border=True):
            st.markdown("#### 🏠 Overview")
            st.markdown(
                "- Filter by airline, class, and destination\n"
                "- 5 KPI cards with comparison arrows\n"
                "- Average fare by airline\n"
                "- How fares change as departure gets closer"
            )
    with p2:
        with st.container(border=True):
            st.markdown("#### 🔍 Check Flight")
            st.markdown(
                "- Pick a route and filter flights live\n"
                "- Class, airline, stops, time, and fare range\n"
                "- Best deal highlight and summary cards\n"
                "- Sortable table with CSV download\n"
                "- Price vs duration chart"
            )
    with p3:
        with st.container(border=True):
            st.markdown("#### 📊 Analytics")
            st.markdown(
                "- Flights share by airline and destination\n"
                "- Fare by departure time and number of stops\n"
                "- Destination × time heatmap\n"
                "- Auto-generated insights"
            )

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("🛠️ Tech stack")
            st.markdown(
                "| Layer | Tools |\n"
                "|---|---|\n"
                "| Language | Python |\n"
                "| Web app | Streamlit, streamlit-option-menu |\n"
                "| Database | MySQL, mysql-connector-python |\n"
                "| Data handling | pandas |\n"
                "| Charts | Plotly |"
            )
    with right:
        with st.container(border=True):
            st.subheader("⚙️ How it works")
            st.graphviz_chart(
                """
                digraph {
                    rankdir=LR; bgcolor="transparent";
                    node [shape=box, style="rounded,filled", fillcolor="#1A1F2B",
                          color="#00C2FF", fontcolor="white", fontname="Arial", fontsize=11];
                    edge [color="#94A3B8"];
                    MySQL -> "dbhelper.py" -> "Cache" -> "pandas" -> "Plotly charts";
                }
                """,
                use_container_width=True,
            )
            st.markdown(
                "`dbhelper.py` runs the SQL queries, results are cached so the app stays fast, "
                "pandas applies your filters instantly, and Plotly draws the charts."
            )

    with st.container(border=True):
        st.subheader("💻 Run it locally")
        st.code(
            "pip install streamlit streamlit-option-menu plotly pandas mysql-connector-python\n"
            "streamlit run app.py",
            language="bash",
        )
        st.caption("Database settings are read from .st/tv.toml, which is not included in the repository.")

    with st.container(border=True):
        st.subheader("🚀 Future improvements")
        st.markdown(
            "- Load the full dataset with all six source cities\n"
            "- A Compare page for two airlines or routes side by side\n"
            "- A machine-learning fare predictor\n"
            "- Deploy online with Streamlit Community Cloud"
        )