import os
import pandas as pd
import mysql.connector
import streamlit as st


class DB:
    """Opens a fresh connection per query, so a stale or dropped
    connection never breaks the Streamlit app."""

    def __init__(self):
        # Keep credentials out of the code: set these as environment variables
        # (or move them to .streamlit/secrets.toml later).
        self.config = dict(
            host=st.secrets["db"]["host"],
            user=st.secrets["db"]["user"],
            password=st.secrets["db"]["password"],
            database=st.secrets["db"]["database"],
        )

    def _query(self, sql, params=None):
        """Run a query and return (rows, column_names)."""
        conn = mysql.connector.connect(**self.config)
        try:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            cols = [c[0] for c in cur.description]
            cur.close()
            return rows, cols
        finally:
            conn.close()

    # ---------- Check Flight ----------
    def fetch_city_name(self):
        rows, _ = self._query("""
            SELECT source_city FROM flight
            UNION
            SELECT destination_city FROM flight
        """)
        return [r[0] for r in rows]

    def fetch_all_flight(self, source, destination):
        rows, cols = self._query(
            """
            SELECT airline, flight, departure_time, arrival_time, stops,
                   class, duration, days_left, price
            FROM flight
            WHERE source_city = %s AND destination_city = %s
            ORDER BY price
            """,
            (source, destination),
        )
        return pd.DataFrame(rows, columns=cols)

    # ---------- Analytics ----------
    def fetch_airline_frequency(self):
        rows, _ = self._query("""
            SELECT airline, COUNT(*) FROM flight
            GROUP BY airline
            ORDER BY COUNT(*) DESC
        """)
        return [r[0] for r in rows], [r[1] for r in rows]

    def busiest_airport(self):
        rows, _ = self._query("""
            SELECT city, COUNT(*) AS total FROM (
                SELECT source_city AS city FROM flight
                UNION ALL
                SELECT destination_city FROM flight
            ) AS t
            GROUP BY city
            ORDER BY total DESC
        """)
        return [r[0] for r in rows], [r[1] for r in rows]

    # ---------- Dropdown lists ----------
    def fetch_source_cities(self):
        rows, _ = self._query("SELECT DISTINCT source_city FROM flight")
        return [r[0] for r in rows]

    def fetch_destination_cities(self):
        rows, _ = self._query("SELECT DISTINCT destination_city FROM flight")
        return [r[0] for r in rows]

    def fetch_destinations_from(self, source):
        """Only destinations that actually have flights from this source."""
        rows, _ = self._query(
            "SELECT DISTINCT destination_city FROM flight WHERE source_city = %s", (source,)
        )
        return [r[0] for r in rows]

    # ---------- Overview ----------
    @staticmethod
    def _where(airline="All", flight_class="All", destination="All"):
        """Build a WHERE clause from the dropdown filters ('All' = no filter)."""
        clauses, params = [], []
        for col, val in (("airline", airline), ("class", flight_class), ("destination_city", destination)):
            if val != "All":
                clauses.append(f"`{col}` = %s")
                params.append(val)
        sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return sql, tuple(params)

    def fetch_classes(self):
        rows, _ = self._query("SELECT DISTINCT class FROM flight ORDER BY class")
        return [r[0] for r in rows]

    def kpis(self, airline="All", flight_class="All", destination="All"):
        where, params = self._where(airline, flight_class, destination)
        rows, cols = self._query(
            f"""
            SELECT COUNT(*)                 AS total_flights,
                   ROUND(AVG(price))        AS avg_price,
                   MIN(price)               AS min_price,
                   ROUND(AVG(duration), 1)  AS avg_duration
            FROM flight {where}
            """,
            params,
        )
        result = dict(zip(cols, rows[0]))

        rows, _ = self._query(
            f"""
            SELECT destination_city, COUNT(*) AS n FROM flight {where}
            GROUP BY destination_city ORDER BY n DESC LIMIT 1
            """,
            params,
        )
        result["top_destination"] = rows[0][0] if rows else "-"
        return result

    def avg_price_by_airline(self, flight_class="All", destination="All"):
        # airline filter is skipped on purpose, so every airline stays visible
        where, params = self._where("All", flight_class, destination)
        rows, cols = self._query(
            f"""
            SELECT airline, ROUND(AVG(price)) AS avg_price
            FROM flight {where}
            GROUP BY airline ORDER BY avg_price DESC
            """,
            params,
        )
        return pd.DataFrame(rows, columns=cols)

    def price_by_days_left(self, airline="All", flight_class="All", destination="All"):
        where, params = self._where(airline, flight_class, destination)
        rows, cols = self._query(
            f"""
            SELECT days_left, ROUND(AVG(price)) AS avg_price
            FROM flight {where}
            GROUP BY days_left ORDER BY days_left
            """,
            params,
        )
        return pd.DataFrame(rows, columns=cols)

    # ---------- Analytics page (aggregated) ----------
    def analytics_data(self):
        """One small grouped table (airline x destination x class x stops x time).
        The app filters and re-aggregates it in pandas, so charts update instantly."""
        rows, cols = self._query("""
            SELECT airline, destination_city, class, stops, departure_time,
                   COUNT(*)      AS flights,
                   SUM(price)    AS total_price,
                   SUM(duration) AS total_duration
            FROM flight
            GROUP BY airline, destination_city, class, stops, departure_time
        """)
        df = pd.DataFrame(rows, columns=cols)
        df["flights"] = df["flights"].astype(int)
        df["total_price"] = df["total_price"].astype(float)
        df["total_duration"] = df["total_duration"].astype(float)
        return df