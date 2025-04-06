import streamlit as st
import sqlite3
import time
from datetime import datetime, timedelta
import hashlib
from typing import Optional, Tuple, List, Dict

# Database setup
def init_db():
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  email TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Study sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS study_sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  title TEXT NOT NULL,
                  description TEXT,
                  start_time TIMESTAMP NOT NULL,
                  end_time TIMESTAMP,
                  duration INTEGER,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # Groups table
    c.execute('''CREATE TABLE IF NOT EXISTS groups
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  description TEXT,
                  created_by INTEGER NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (created_by) REFERENCES users (id))''')
    
    # Group members table
    c.execute('''CREATE TABLE IF NOT EXISTS group_members
                 (group_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (group_id, user_id),
                  FOREIGN KEY (group_id) REFERENCES groups (id),
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    conn.commit()
    conn.close()

# Password hashing
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Authentication functions
def signup(username: str, password: str, email: str = None) -> bool:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                 (username, hash_password(password), email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login(username: str, password: str) -> Optional[int]:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    
    if result and result[1] == hash_password(password):
        return result[0]  # Return user_id
    return None

# Study session functions
def start_study_session(user_id: int, title: str, description: str = None) -> int:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute("INSERT INTO study_sessions (user_id, title, description, start_time) VALUES (?, ?, ?, ?)",
              (user_id, title, description, datetime.now()))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def end_study_session(session_id: int) -> None:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    
    # Get start time
    c.execute("SELECT start_time FROM study_sessions WHERE id = ?", (session_id,))
    start_time = datetime.strptime(c.fetchone()[0], "%Y-%m-%d %H:%M:%S.%f")
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Update session
    c.execute("UPDATE study_sessions SET end_time = ?, duration = ? WHERE id = ?",
              (end_time, duration, session_id))
    conn.commit()
    conn.close()

def get_study_sessions(user_id: int, limit: int = None) -> List[Dict]:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    
    query = """SELECT id, title, description, start_time, end_time, duration 
               FROM study_sessions 
               WHERE user_id = ? 
               ORDER BY start_time DESC"""
    if limit:
        query += f" LIMIT {limit}"
    
    c.execute(query, (user_id,))
    sessions = []
    for row in c.fetchall():
        sessions.append({
            'id': row[0],
            'title': row[1],
            'description': row[2],
            'start_time': row[3],
            'end_time': row[4],
            'duration': row[5]
        })
    conn.close()
    return sessions

def get_total_study_time(user_id: int) -> float:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute("SELECT SUM(duration) FROM study_sessions WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0] or 0
    conn.close()
    return total

# Group functions
def create_group(name: str, description: str, created_by: int) -> int:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute("INSERT INTO groups (name, description, created_by) VALUES (?, ?, ?)",
              (name, description, created_by))
    group_id = c.lastrowid
    # Add creator as member
    c.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
              (group_id, created_by))
    conn.commit()
    conn.close()
    return group_id

def get_user_groups(user_id: int) -> List[Dict]:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute("""SELECT g.id, g.name, g.description, g.created_by, u.username 
                 FROM groups g
                 JOIN group_members gm ON g.id = gm.group_id
                 JOIN users u ON g.created_by = u.id
                 WHERE gm.user_id = ?""", (user_id,))
    groups = []
    for row in c.fetchall():
        groups.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'created_by': row[3],
            'creator_name': row[4]
        })
    conn.close()
    return groups

def get_all_groups(user_id: int) -> List[Dict]:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    # Get all groups not joined by the user
    c.execute("""SELECT g.id, g.name, g.description, g.created_by, u.username 
                 FROM groups g
                 JOIN users u ON g.created_by = u.id
                 WHERE g.id NOT IN 
                    (SELECT group_id FROM group_members WHERE user_id = ?)""", (user_id,))
    groups = []
    for row in c.fetchall():
        groups.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'created_by': row[3],
            'creator_name': row[4]
        })
    conn.close()
    return groups

def join_group(group_id: int, user_id: int) -> bool:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                  (group_id, user_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def leave_group(group_id: int, user_id: int) -> None:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
              (group_id, user_id))
    conn.commit()
    conn.close()

def get_group_members_stats(group_id: int) -> List[Dict]:
    conn = sqlite3.connect('study_tracker.db')
    c = conn.cursor()
    c.execute("""SELECT u.id, u.username, COALESCE(SUM(s.duration), 0) as total_time
                 FROM users u
                 JOIN group_members gm ON u.id = gm.user_id
                 LEFT JOIN study_sessions s ON u.id = s.user_id
                 WHERE gm.group_id = ?
                 GROUP BY u.id, u.username
                 ORDER BY total_time DESC""", (group_id,))
    members = []
    for row in c.fetchall():
        members.append({
            'user_id': row[0],
            'username': row[1],
            'total_time': row[2]
        })
    conn.close()
    return members

# Streamlit UI
def main():
    st.set_page_config(page_title="Study Tracker", layout="wide")
    init_db()
    
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'current_session' not in st.session_state:
        st.session_state.current_session = None
    if 'page' not in st.session_state:
        st.session_state.page = "login"
    
    # Navigation
    if st.session_state.user_id:
        cols = st.columns(5)
        if cols[0].button("Study Timer"):
            st.session_state.page = "timer"
        if cols[1].button("Study History"):
            st.session_state.page = "history"
        if cols[2].button("My Groups"):
            st.session_state.page = "my_groups"
        if cols[3].button("All Groups"):
            st.session_state.page = "all_groups"
        if cols[4].button("Logout"):
            st.session_state.user_id = None
            st.session_state.page = "login"
            st.rerun()
    
    # Pages
    if st.session_state.page == "login":
        login_page()
    elif st.session_state.page == "signup":
        signup_page()
    elif st.session_state.page == "timer":
        timer_page()
    elif st.session_state.page == "history":
        history_page()
    elif st.session_state.page == "my_groups":
        my_groups_page()
    elif st.session_state.page == "all_groups":
        all_groups_page()

def login_page():
    st.title("Study Tracker - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            user_id = login(username, password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.page = "timer"
                st.rerun()
            else:
                st.error("Invalid username or password")
    
    if st.button("Don't have an account? Sign up"):
        st.session_state.page = "signup"
        st.rerun()

def signup_page():
    st.title("Study Tracker - Sign Up")
    
    with st.form("signup_form"):
        username = st.text_input("Username")
        email = st.text_input("Email (optional)")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit = st.form_submit_button("Sign Up")
        
        if submit:
            if password != confirm_password:
                st.error("Passwords don't match")
            else:
                if signup(username, password, email):
                    st.success("Account created successfully! Please login.")
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.error("Username already exists")
    
    if st.button("Back to Login"):
        st.session_state.page = "login"
        st.rerun()

def timer_page():
    st.title("Study Timer")
    
    if st.session_state.current_session:
        session = get_study_sessions(st.session_state.user_id, limit=1)[0]
        st.subheader(f"Current Session: {session['title']}")
        if session['description']:
            st.write(session['description'])
        
        # Get the start time from the session
        start_time = datetime.strptime(session['start_time'], "%Y-%m-%d %H:%M:%S.%f")
        elapsed_time = datetime.now() - start_time
        elapsed_str = str(elapsed_time).split('.')[0]
        
        # Display the timer (will update on each rerun)
        st.metric("Elapsed Time", elapsed_str)
        
        # Use a form for the end session button to prevent premature reruns
        with st.form("end_session_form"):
            if st.form_submit_button("End Session"):
                end_study_session(session['id'])
                st.session_state.current_session = None
                st.success("Session saved!")
                time.sleep(1)
                st.rerun()
        
        # Auto-rerun every second to update the timer
        time.sleep(1)
        st.rerun()
            
    else:
        with st.form("new_session_form"):
            title = st.text_input("Session Title", placeholder="What are you studying?")
            description = st.text_area("Description (optional)", placeholder="Details about this session")
            submit = st.form_submit_button("Start Study Session")
            
            if submit and title:
                session_id = start_study_session(st.session_state.user_id, title, description)
                st.session_state.current_session = session_id
                st.rerun()
    
    # Display recent sessions
    st.subheader("Recent Sessions")
    sessions = get_study_sessions(st.session_state.user_id, limit=5)
    if sessions:
        for session in sessions:
            col1, col2 = st.columns([3, 1])
            col1.write(f"**{session['title']}**")
            if session['description']:
                col1.write(session['description'])
            
            if session['duration']:
                duration = str(timedelta(seconds=int(session['duration'])))
                col2.write(f"Duration: {duration}")
            else:
                col2.write("In progress")
            st.divider()
    else:
        st.write("No study sessions yet. Start one above!")

def history_page():
    st.title("Study History")
    
    # Stats
    total_time = get_total_study_time(st.session_state.user_id)
    if total_time:
        st.subheader(f"Total Study Time: {str(timedelta(seconds=int(total_time)))}")
    else:
        st.subheader("No study sessions recorded yet")
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        date_range = st.selectbox("Filter by", ["All time", "Last 7 days", "Last 30 days"])
    with col2:
        sort_by = st.selectbox("Sort by", ["Newest first", "Oldest first", "Longest first", "Shortest first"])
    
    # Get sessions with filters
    sessions = get_study_sessions(st.session_state.user_id)
    
    # Apply date filter
    if date_range != "All time":
        cutoff = datetime.now() - timedelta(days=7 if date_range == "Last 7 days" else 30)
        sessions = [s for s in sessions if datetime.strptime(s['start_time'], "%Y-%m-%d %H:%M:%S.%f") >= cutoff]
    
    # Apply sort
    if sort_by == "Oldest first":
        sessions = sorted(sessions, key=lambda x: x['start_time'])
    elif sort_by == "Longest first":
        sessions = sorted(sessions, key=lambda x: x['duration'] or 0, reverse=True)
    elif sort_by == "Shortest first":
        sessions = sorted(sessions, key=lambda x: x['duration'] or float('inf'))
    else:  # Newest first (default)
        sessions = sorted(sessions, key=lambda x: x['start_time'], reverse=True)
    
    # Display sessions
    if sessions:
        for session in sessions:
            col1, col2 = st.columns([3, 1])
            col1.write(f"**{session['title']}**")
            col1.write(f"*{session['start_time']}*")
            if session['description']:
                col1.write(session['description'])
            
            if session['duration']:
                duration = str(timedelta(seconds=int(session['duration'])))
                col2.write(f"**{duration}**")
            else:
                col2.write("In progress")
            st.divider()
    else:
        st.write("No study sessions found with these filters.")

def my_groups_page():
    st.title("My Study Groups")
    
    # Create new group
    with st.expander("Create New Group"):
        with st.form("create_group_form"):
            name = st.text_input("Group Name")
            description = st.text_area("Description")
            submit = st.form_submit_button("Create Group")
            
            if submit and name:
                group_id = create_group(name, description, st.session_state.user_id)
                st.success(f"Group '{name}' created!")
                time.sleep(1)
                st.rerun()
    
    # User's groups
    groups = get_user_groups(st.session_state.user_id)
    if groups:
        for group in groups:
            col1, col2 = st.columns([4, 1])
            col1.subheader(group['name'])
            col1.write(group['description'])
            col1.write(f"Created by: {group['creator_name']}")
            
            if col2.button("Leave", key=f"leave_{group['id']}"):
                leave_group(group['id'], st.session_state.user_id)
                st.success(f"Left group '{group['name']}'")
                time.sleep(1)
                st.rerun()
            
            # Group stats
            st.subheader("Member Stats")
            members = get_group_members_stats(group['id'])
            for i, member in enumerate(members, 1):
                time_str = str(timedelta(seconds=int(member['total_time'])))
                st.write(f"{i}. {member['username']}: {time_str}")
            
            st.divider()
    else:
        st.write("You haven't joined any groups yet. Join one from the All Groups page!")

def all_groups_page():
    st.title("All Study Groups")
    
    groups = get_all_groups(st.session_state.user_id)
    if groups:
        for group in groups:
            col1, col2 = st.columns([4, 1])
            col1.subheader(group['name'])
            col1.write(group['description'])
            col1.write(f"Created by: {group['creator_name']}")
            
            if col2.button("Join", key=f"join_{group['id']}"):
                if join_group(group['id'], st.session_state.user_id):
                    st.success(f"Joined group '{group['name']}'")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to join group")
            
            st.divider()
    else:
        st.write("No groups available to join or you've already joined all groups.")

if __name__ == "__main__":
    main()