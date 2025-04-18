import streamlit as st
import sqlite3
import time
from datetime import datetime, timedelta
import hashlib
from typing import Optional, Tuple, List, Dict

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

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

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
        return result[0]  
    return None

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
    col1, col2, col3 = st.columns([1, 2, 1])  # Corrected column distribution

    with col2:
        st.title("Study Tracker Login")

        with st.form("login_form"):
            st.markdown("### 👤 Username")
            username = st.text_input(" ", placeholder="Enter your username", key="login_username")

            st.markdown(" ")  

            st.markdown("### 🔑 Password")
            password = st.text_input(" ", type="password", placeholder="••••••••", key="login_password")
            st.markdown("")
            st.markdown("")
            st.markdown("")
            if st.form_submit_button("🚀 Login", use_container_width=True):
                if not username or not password:
                    st.error("Username and password are required!")
                else:
                    user_id = login(username, password)
                    if user_id:
                        st.session_state.user_id = user_id
                        st.session_state.page = "timer"
                        st.rerun()
                    else:
                        st.error("Invalid credentials")

        st.markdown("")  

        st.button("Sign Up", on_click=lambda: setattr(st.session_state, 'page', 'signup'))


def signup_page():
    col1, col2, col3 = st.columns([1, 2, 1])  # Center the form

    with col2:
        st.title("Create Account")

        with st.form("signup_form"):
            st.markdown("### 👤 Username")
            username = st.text_input(" ", placeholder="Choose a username", key="username",label_visibility="hidden")

            st.markdown("### 📧 Email (optional)")
            email = st.text_input(" ", placeholder="user@example.com", key="email",label_visibility="hidden")

            st.markdown("### 🔑 Password")
            password = st.text_input(" ", type="password", placeholder="••••••••", key="password",label_visibility="hidden")

            st.markdown("### ✅ Confirm Password")
            confirm = st.text_input(" ", type="password", placeholder="••••••••", key="confirm",label_visibility="hidden")
            st.markdown("")
            st.markdown("")
            if st.form_submit_button("🚀 Create Account", use_container_width=True):
                if not username or not password:
                    st.error("Username and password are required!")
                elif password != confirm:
                    st.error("Passwords don't match!")
                elif signup(username, password, email):
                    st.success("Account created! Please login")
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.error("Username already exists")

        st.button("Back to Login", on_click=lambda: setattr(st.session_state, 'page', 'login'))

import time
from datetime import datetime, timedelta
import streamlit as st

def timer_page():
    st.title("⏳Study Timer")
    
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
    st.title("📚 Study History")
    
    # 1. Get all sessions (unfiltered)
    all_sessions = get_study_sessions(st.session_state.user_id)
    
    # 2. Date Filter (Sidebar)
    with st.sidebar:
        st.header("🔍 Filters")
        date_filter = st.selectbox(
            "Time Period",
            ["All Time", "Today", "Last 7 Days", "Last 30 Days", "Custom Range"],
            key="date_filter"
        )
        
        custom_start = None
        custom_end = None
        if date_filter == "Custom Range":
            col1, col2 = st.columns(2)
            custom_start = col1.date_input("Start Date", value=datetime.now() - timedelta(days=30))
            custom_end = col2.date_input("End Date", value=datetime.now())
    
    # 3. Apply Filters
    filtered_sessions = []
    now = datetime.now()
    
    for session in all_sessions:
        session_time = datetime.strptime(session['start_time'], "%Y-%m-%d %H:%M:%S.%f")
        
        if date_filter == "All Time":
            filtered_sessions.append(session)
        elif date_filter == "Today" and session_time.date() == now.date():
            filtered_sessions.append(session)
        elif date_filter == "Last 7 Days" and session_time >= (now - timedelta(days=7)):
            filtered_sessions.append(session)
        elif date_filter == "Last 30 Days" and session_time >= (now - timedelta(days=30)):
            filtered_sessions.append(session)
        elif date_filter == "Custom Range" and custom_start and custom_end:
            if custom_start <= session_time.date() <= custom_end:
                filtered_sessions.append(session)
    
    # 4. Calculate Filtered Total Time (including seconds)
    total_seconds = sum(session['duration'] for session in filtered_sessions if session['duration'])
    total_time_str = str(timedelta(seconds=int(total_seconds)))  # Formats as "H:MM:SS"
    
    # 5. Display Stats Header
    if total_seconds > 0:
        st.subheader(f"⏳ Total Study Time: **{total_time_str}**")
        st.caption(f"Showing {len(filtered_sessions)} sessions")
    else:
        st.warning("No study sessions found for selected filters")
    
    # 6. Display Sessions in Cards (with seconds)
    if filtered_sessions:
        for session in filtered_sessions:
            with st.container(border=True):
                cols = st.columns([4, 1])
                
                # Left Column: Session Info
                with cols[0]:
                    st.markdown(f"### {session['title']}")
                    if session['description']:
                        st.caption(f"📝 {session['description']}")
                    
                    start_time = datetime.strptime(session['start_time'], "%Y-%m-%d %H:%M:%S.%f")
                    date_str = start_time.strftime("%a, %b %d %Y")
                    time_str = start_time.strftime("%I:%M %p")
                    st.caption(f"🗓️ {date_str} | 🕒 {time_str}")
                
                # Right Column: Duration (with seconds)
                with cols[1]:
                    if session['duration']:
                        duration_str = str(timedelta(seconds=int(session['duration'])))
                        st.metric(
                            "Duration", 
                            f"{duration_str}",
                            help="HH:MM:SS format"
                        )
                    else:
                        st.warning("Incomplete")
    
    # 7. Empty State
    else:
        st.info("No sessions match your current filters. Try adjusting the date range.")

def my_groups_page():
    st.title("👥 My Study Groups")
    
    # Search functionality
    search_query = st.text_input("🔍 Search my groups", placeholder="Find a group...")
    
    # Create group expander
    with st.expander("➕ Create New Group", expanded=False):
        with st.form("create_group"):
            name = st.text_input("Group name")
            desc = st.text_area("Description")
            if st.form_submit_button("Create", use_container_width=True):
                create_group(name, desc, st.session_state.user_id)
                st.rerun()
    
    # Display groups with filtering
    groups = [g for g in get_user_groups(st.session_state.user_id) 
              if search_query.lower() in g['name'].lower()]
    
    if groups:
        for group in groups:
            with st.container(border=True):
                cols = st.columns([4,1])
                cols[0].subheader(group['name'])
                cols[0].caption(f"👤 Created by: {group['creator_name']}")
                if group['description']:
                    cols[0].write(group['description'])
                
                if cols[1].button("Leave", key=f"leave_{group['id']}"):
                    leave_group(group['id'], st.session_state.user_id)
                    st.rerun()
                
                # Member stats
                with st.expander(f"👥 Members ({len(get_group_members_stats(group['id']))})"):
                    for member in get_group_members_stats(group['id']):
                        st.write(f"- {member['username']}: {timedelta(seconds=member['total_time'])}")
    else:
        st.info("No groups found" if search_query else "You haven't joined any groups yet")

def all_groups_page():
    st.title("🌐 All Study Groups")
    
    # Search and filter
    col1, col2 = st.columns([3,1])
    search_query = col1.text_input("🔍 Search all groups", placeholder="Find a group to join...")
    sort_by = col2.selectbox("Sort by", ["Newest", "Most Members"])
    
    groups = get_all_groups(st.session_state.user_id)
    
    # Apply search and sort
    if search_query:
        groups = [g for g in groups if search_query.lower() in g['name'].lower()]
    
    if sort_by == "Most Members":
        groups.sort(key=lambda g: len(get_group_members_stats(g['id'])), reverse=True)
    
    # Display groups
    if groups:
        for group in groups:
            with st.container(border=True):
                cols = st.columns([4,1])
                cols[0].subheader(group['name'])
                cols[0].caption(f"👤 Created by: {group['creator_name']}")
                if group['description']:
                    cols[0].write(group['description'])
                
                members = get_group_members_stats(group['id'])
                cols[0].caption(f"👥 {len(members)} members")
                
                if cols[1].button("Join", key=f"join_{group['id']}"):
                    join_group(group['id'], st.session_state.user_id)
                    st.rerun()
    else:
        st.info("No groups available" if search_query else "No groups found to join")

def history_page():
    st.title("📚 Study History")
    
    # 1. Get all sessions (unfiltered)
    all_sessions = get_study_sessions(st.session_state.user_id)
    
    # 2. Date Filter (Sidebar)
    with st.sidebar:
        st.header("🔍 Filters")
        date_filter = st.selectbox(
            "Time Period",
            ["All Time", "Today", "Last 7 Days", "Last 30 Days", "Custom Range"],
            key="date_filter"
        )
        
        custom_start = None
        custom_end = None
        if date_filter == "Custom Range":
            col1, col2 = st.columns(2)
            custom_start = col1.date_input("Start Date", value=datetime.now() - timedelta(days=30))
            custom_end = col2.date_input("End Date", value=datetime.now())
    
    # 3. Apply Filters
    filtered_sessions = []
    now = datetime.now()
    
    for session in all_sessions:
        session_time = datetime.strptime(session['start_time'], "%Y-%m-%d %H:%M:%S.%f")
        
        if date_filter == "All Time":
            filtered_sessions.append(session)
        elif date_filter == "Today" and session_time.date() == now.date():
            filtered_sessions.append(session)
        elif date_filter == "Last 7 Days" and session_time >= (now - timedelta(days=7)):
            filtered_sessions.append(session)
        elif date_filter == "Last 30 Days" and session_time >= (now - timedelta(days=30)):
            filtered_sessions.append(session)
        elif date_filter == "Custom Range" and custom_start and custom_end:
            if custom_start <= session_time.date() <= custom_end:
                filtered_sessions.append(session)
    
    # 4. Calculate Filtered Total Time
    total_seconds = sum(session['duration'] for session in filtered_sessions if session['duration'])
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # 5. Display Stats Header
    if total_seconds > 0:
        st.subheader(f"⏳ Total Filtered Study Time: **{hours}h {minutes}m**")
        st.caption(f"Showing {len(filtered_sessions)} sessions")
    else:
        st.warning("No study sessions found for selected filters")
    
    # 6. Display Sessions in Cards
    if filtered_sessions:
        for session in filtered_sessions:
            with st.container(border=True):
                cols = st.columns([4, 1])
                
                # Left Column: Session Info
                with cols[0]:
                    st.markdown(f"### {session['title']}")
                    if session['description']:
                        st.caption(f"📝 {session['description']}")
                    
                    start_time = datetime.strptime(session['start_time'], "%Y-%m-%d %H:%M:%S.%f")
                    date_str = start_time.strftime("%a, %b %d %Y")
                    time_str = start_time.strftime("%I:%M %p")
                    st.caption(f"🗓️ {date_str} | 🕒 {time_str}")
                
                # Right Column: Duration
                with cols[1]:
                    if session['duration']:
                        dur_h, rem = divmod(session['duration'], 3600)
                        dur_m, _ = divmod(rem, 60)
                        st.metric(
                            "Duration", 
                            f"{int(dur_h)}h {int(dur_m)}m",
                            help="Session length"
                        )
                    else:
                        st.warning("Incomplete")
    
    # 7. Empty State
    else:
        st.info("No sessions match your current filters. Try adjusting the date range.")


if __name__ == "__main__":
    main()