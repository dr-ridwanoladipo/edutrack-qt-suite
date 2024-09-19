import streamlit as st
import sqlite3
import pandas as pd
import os
import re

# Set page config at the very beginning
st.set_page_config(page_title="Student Management System", layout="wide")

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
    /* Custom width for ID column */
    [data-testid="stDataFrameResizable"] table td:first-child,
    [data-testid="stDataFrameResizable"] table th:first-child {
        width: 50px !important;
        min-width: 50px !important;
        max-width: 50px !important;
    }
</style>
""", unsafe_allow_html=True)

# Database setup
DB_FILE = 'students.db'


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY, name TEXT)''')
    conn.commit()
    conn.close()


def load_data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM students", conn)
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
        # Get current columns
        c.execute("PRAGMA table_info(students)")
        current_columns = [row[1] for row in c.fetchall()]

        # Add new columns
        for col in new_columns:
            if col not in current_columns and col != 'id':
                safe_col = sanitize_column_name(col)
                c.execute(f"ALTER TABLE students ADD COLUMN {safe_col} TEXT")

        # Create new table with desired schema
        new_cols = ', '.join(
            [f"{sanitize_column_name(col)} {'INTEGER PRIMARY KEY' if col == 'id' else 'TEXT'}" for col in new_columns])
        c.execute(f"CREATE TABLE new_students ({new_cols})")

        # Copy data to new table
        old_cols = ', '.join([sanitize_column_name(col) for col in new_columns if col in current_columns])
        c.execute(f"INSERT INTO new_students ({old_cols}) SELECT {old_cols} FROM students")

        # Replace old table with new table
        c.execute("DROP TABLE students")
        c.execute("ALTER TABLE new_students RENAME TO students")

        conn.commit()
        return True
    except sqlite3.Error as e:
        st.error(f"Error updating database schema: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    st.title("Student Management System")

    init_db()
    df = load_data()

    if 'columns' not in st.session_state:
        st.session_state.columns = df.columns.tolist()

    with st.sidebar:
        st.header("Column Configuration")
        st.text_input("Enter column names (comma-separated)",
                      value=','.join(st.session_state.columns),
                      key="column_input")
        if st.button("Update Columns"):
            old_columns = st.session_state.columns
            save_column_config()
            if update_database_schema(old_columns, st.session_state.columns):
                st.success("Columns updated. Database schema has been modified.")
                st.rerun()
            else:
                st.error("Failed to update columns. Please try again.")

    tab1, tab2, tab3, tab4 = st.tabs(["View Students", "Add Student", "Edit Student", "Delete Student"])

    with tab1:
        st.header("Student Records")
        df = load_data()  # Reload data to reflect any changes
        st.dataframe(df, use_container_width=True, key="student_data")
        if st.button("Refresh Data"):
            st.rerun()

    with tab2:
        st.header("Add New Student")
        with st.form("add_student_form"):
            new_student = {}
            for col in st.session_state.columns:
                new_student[sanitize_column_name(col)] = st.text_input(f"Enter {col}")

            submit_button = st.form_submit_button("Add Student")
            if submit_button:
                conn = get_db_connection()
                c = conn.cursor()
                try:
                    columns = ', '.join(new_student.keys())
                    placeholders = ', '.join(['?' for _ in new_student])
                    query = f"INSERT INTO students ({columns}) VALUES ({placeholders})"
                    c.execute(query, tuple(new_student.values()))
                    conn.commit()
                    st.success("Student added successfully!")
                except sqlite3.Error as e:
                    st.error(f"Error adding student: {e}")
                finally:
                    conn.close()

    with tab3:
        st.header("Edit Student")
        edit_id = st.number_input("Enter student ID to edit", min_value=1, step=1)
        load_button = st.button("Load Student Data")

        if load_button:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM students WHERE id = ?", (edit_id,))
            student_data = c.fetchone()
            conn.close()

            if student_data:
                st.session_state.edit_data = dict(student_data)
                st.success(f"Student data for ID {edit_id} loaded successfully.")
            else:
                st.error("Student not found.")

        if 'edit_data' in st.session_state:
            with st.form("edit_student_form"):
                edited_student = {}
                for col in st.session_state.columns:
                    edited_student[sanitize_column_name(col)] = st.text_input(f"Edit {col}",
                                                                              value=st.session_state.edit_data.get(col,
                                                                                                                   ''))

                update_button = st.form_submit_button("Update Student")
                if update_button:
                    conn = get_db_connection()
                    c = conn.cursor()
                    try:
                        update_cols = ', '.join([f"{col} = ?" for col in edited_student.keys() if col != 'id'])
                        query = f"UPDATE students SET {update_cols} WHERE id = ?"
                        values = [v for k, v in edited_student.items() if k != 'id'] + [edited_student['id']]
                        c.execute(query, values)
                        conn.commit()
                        st.success(f"Student with ID {edited_student['id']} updated successfully!")
                    except sqlite3.Error as e:
                        st.error(f"Error updating student: {e}")
                    finally:
                        conn.close()

    with tab4:
        st.header("Delete Student")
        delete_id = st.number_input("Enter student ID to delete", min_value=1, step=1)
        if st.button("Delete Student"):
            conn = get_db_connection()
            c = conn.cursor()
            try:
                c.execute("DELETE FROM students WHERE id = ?", (delete_id,))
                if c.rowcount > 0:
                    conn.commit()
                    st.success(f"Student with ID {delete_id} deleted successfully!")
                else:
                    st.warning(f"No student found with ID {delete_id}.")
            except sqlite3.Error as e:
                st.error(f"Error deleting student: {e}")
            finally:
                conn.close()

    st.markdown("---")
    st.markdown("© 2024 Student Management System.All rights reserved.")


if __name__ == "__main__":
    main()
