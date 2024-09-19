import streamlit as st
import sqlite3
import pandas as pd
import time
import os
import re
import json

# Set page config at the very beginning
st.set_page_config(page_title="Adaptable Management System", layout="wide")

# Custom CSS for improved visual appeal
st.markdown("""
<style>
    .stApp {
        background-color: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 960px;
        background-color: white;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    h1 {
        color: #2c3e50;
        text-align: center;
        padding-bottom: 1rem;
        border-bottom: 2px solid #3498db;
    }
    .stButton>button {
        background-color: #3498db;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stTextInput>div>div>input {
        background-color: #f9f9f9;
        border: 1px solid #bdc3c7;
        border-radius: 5px;
    }
    .stTab {
        background-color: #ecf0f1;
        border-radius: 5px 5px 0 0;
    }
    [data-testid="stSidebar"] {
        background-color: #2c3e50;
        padding: 2rem 1rem;
    }
    [data-testid="stSidebar"] .stTextInput>div>div>input {
        background-color: #34495e;
        color: white;
        border: 1px solid #4a6f8b;
    }
    [data-testid="stSidebar"] .stMarkdown {
        color: #ecf0f1;
    }
    [data-testid="stSidebar"] h2 {
        color: #3498db;
    }
    /* Custom width for ID column */
    [data-testid="stDataFrameResizable"] table td:first-child,
    [data-testid="stDataFrameResizable"] table th:first-child {
        width: 50px !important;
        min-width: 50px !important;
        max-width: 50px !important;
    }
</style>
""", unsafe_allow_html=True)


# New function to load configurations from JSON
def load_config():
    if os.path.exists('app_config.json'):
        with open('app_config.json', 'r') as f:
            return json.load(f)
    return {
        "app_title": "Adaptable Management System",
        "record_name": "Record",
        "tab_names": ["View Records", "Add Record", "Edit Record", "Delete Record"],
        "columns": ['id', 'name']
    }


# New function to save configurations to JSON
def save_config(config):
    with open('app_config.json', 'w') as f:
        json.dump(config, f)


# Database setup
DB_FILE = 'data.db'


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS records
                 (id INTEGER PRIMARY KEY, name TEXT)''')
    conn.commit()
    conn.close()


def load_data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM records", conn)
    conn.close()
    return df


def save_column_config():
    columns = [col.strip() for col in st.session_state.column_input.split(',') if col.strip()]
    if 'id' not in columns:
        columns = ['id'] + columns
    st.session_state.columns = columns


def sanitize_column_name(name):
    return re.sub(r'\W+', '_', name).lower()


def update_database_schema(old_columns, new_columns):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(records)")
        current_columns = [row[1] for row in c.fetchall()]

        for col in new_columns:
            if col not in current_columns and col != 'id':
                safe_col = sanitize_column_name(col)
                c.execute(f"ALTER TABLE records ADD COLUMN {safe_col} TEXT")

        new_cols = ', '.join(
            [f"{sanitize_column_name(col)} {'INTEGER PRIMARY KEY' if col == 'id' else 'TEXT'}" for col in new_columns])
        c.execute(f"CREATE TABLE new_records ({new_cols})")

        old_cols = ', '.join([sanitize_column_name(col) for col in new_columns if col in current_columns])
        c.execute(f"INSERT INTO new_records ({old_cols}) SELECT {old_cols} FROM records")

        c.execute("DROP TABLE records")
        c.execute("ALTER TABLE new_records RENAME TO records")

        conn.commit()
        return True
    except sqlite3.Error as e:
        st.error(f"Error updating database schema: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    # Load configurations
    config = load_config()

    # Initialize session state with loaded configurations
    if 'app_title' not in st.session_state:
        st.session_state.app_title = config['app_title']
    if 'record_name' not in st.session_state:
        st.session_state.record_name = config['record_name']
    if 'tab_names' not in st.session_state:
        st.session_state.tab_names = config['tab_names']
    if 'columns' not in st.session_state:
        st.session_state.columns = config['columns']

    # Sidebar for customization
    with st.sidebar:
        st.header("Customization")
        new_app_title = st.text_input("App Title", value=st.session_state.app_title)
        new_record_name = st.text_input("Record Name", value=st.session_state.record_name)
        new_tab_names = []
        for i, tab in enumerate(st.session_state.tab_names):
            new_tab_names.append(st.text_input(f"Tab {i + 1} Name", value=tab))

        st.header("Column Configuration")
        new_columns = st.text_input("Enter column names (comma-separated)",
                                    value=','.join(st.session_state.columns),
                                    key="column_input")

        if st.button("Save Customizations"):
            st.session_state.app_title = new_app_title
            st.session_state.record_name = new_record_name
            st.session_state.tab_names = new_tab_names
            st.session_state.columns = [col.strip() for col in new_columns.split(',') if col.strip()]
            if 'id' not in st.session_state.columns:
                st.session_state.columns = ['id'] + st.session_state.columns

            # Save to JSON
            save_config({
                "app_title": st.session_state.app_title,
                "record_name": st.session_state.record_name,
                "tab_names": st.session_state.tab_names,
                "columns": st.session_state.columns
            })

            # Update database schema
            if update_database_schema(config['columns'], st.session_state.columns):
                st.success("Customizations saved and database schema updated.")
                st.rerun()
            else:
                st.error("Failed to update database schema. Customizations saved.")

    # Main content
    st.title(st.session_state.app_title)

    init_db()

    tabs = st.tabs(st.session_state.tab_names)

    with tabs[0]:
        st.header(f"View {st.session_state.record_name}s")
        search_term = st.text_input("Search records")

        # Create a placeholder for the dataframe
        data_placeholder = st.empty()

        # Function to load and display data
        def load_and_display_data():
            df = load_data()
            if search_term:
                df = df[df.astype(str).apply(lambda row: row.str.contains(search_term, case=False).any(), axis=1)]
            data_placeholder.dataframe(df, use_container_width=True)

        # Initial data load
        load_and_display_data()

        # Refresh button with loading animation
        if st.button("Refresh Data"):
            with st.spinner('Refreshing data...'):
                time.sleep(0.5)  # Simulate a brief loading time
                load_and_display_data()
            st.success('Data refreshed successfully!')

    with tabs[1]:
        st.header(f"Add New {st.session_state.record_name}")
        with st.form("add_record_form"):
            new_record = {}
            for col in st.session_state.columns:
                new_record[sanitize_column_name(col)] = st.text_input(f"Enter {col}")

            submit_button = st.form_submit_button(f"Add {st.session_state.record_name}")
            if submit_button:
                conn = get_db_connection()
                c = conn.cursor()
                try:
                    columns = ', '.join(new_record.keys())
                    placeholders = ', '.join(['?' for _ in new_record])
                    query = f"INSERT INTO records ({columns}) VALUES ({placeholders})"
                    c.execute(query, tuple(new_record.values()))
                    conn.commit()
                    st.success(f"{st.session_state.record_name} added successfully!")
                except sqlite3.Error as e:
                    st.error(f"Error adding {st.session_state.record_name.lower()}: {e}")
                finally:
                    conn.close()

    with tabs[2]:
        st.header(f"Edit {st.session_state.record_name}")
        edit_id = st.number_input(f"Enter {st.session_state.record_name} ID to edit", min_value=1, step=1)
        load_button = st.button("Load Record Data")

        if load_button:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM records WHERE id = ?", (edit_id,))
            record_data = c.fetchone()
            conn.close()

            if record_data:
                st.session_state.edit_data = dict(record_data)
                st.success(f"{st.session_state.record_name} data for ID {edit_id} loaded successfully.")
            else:
                st.error(f"{st.session_state.record_name} not found.")

        if 'edit_data' in st.session_state:
            with st.form("edit_record_form"):
                edited_record = {}
                for col in st.session_state.columns:
                    edited_record[sanitize_column_name(col)] = st.text_input(f"Edit {col}",
                                                                             value=st.session_state.edit_data.get(col,
                                                                                                                  ''))

                update_button = st.form_submit_button(f"Update {st.session_state.record_name}")
                if update_button:
                    conn = get_db_connection()
                    c = conn.cursor()
                    try:
                        update_cols = ', '.join([f"{col} = ?" for col in edited_record.keys() if col != 'id'])
                        query = f"UPDATE records SET {update_cols} WHERE id = ?"
                        values = [v for k, v in edited_record.items() if k != 'id'] + [edited_record['id']]
                        c.execute(query, values)
                        conn.commit()
                        st.success(
                            f"{st.session_state.record_name} with ID {edited_record['id']} updated successfully!")
                    except sqlite3.Error as e:
                        st.error(f"Error updating {st.session_state.record_name.lower()}: {e}")
                    finally:
                        conn.close()

    with tabs[3]:
        st.header(f"Delete {st.session_state.record_name}")
        delete_id = st.number_input(f"Enter {st.session_state.record_name} ID to delete", min_value=1, step=1)
        if st.button(f"Delete {st.session_state.record_name}"):
            conn = get_db_connection()
            c = conn.cursor()
            try:
                c.execute("DELETE FROM records WHERE id = ?", (delete_id,))
                if c.rowcount > 0:
                    conn.commit()
                    st.success(f"{st.session_state.record_name} with ID {delete_id} deleted successfully!")
                else:
                    st.warning(f"No {st.session_state.record_name.lower()} found with ID {delete_id}.")
            except sqlite3.Error as e:
                st.error(f"Error deleting {st.session_state.record_name.lower()}: {e}")
            finally:
                conn.close()

    # Footer
    st.markdown("---")
    st.markdown(f"© 2024 {st.session_state.app_title}. All rights reserved@dr-ridwan.")


if __name__ == "__main__":
    main()
