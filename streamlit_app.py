from collections import defaultdict
from pathlib import Path
import sqlite3

import streamlit as st
import altair as alt
import pandas as pd


# Set the title and favicon that appear in the Browser's tab bar.
st.set_page_config(
    page_title='Inventory tracker',
    page_icon=':shopping_bags:', # This is an emoji shortcode. Could be a URL too.
)


# -----------------------------------------------------------------------------
# Declare some useful functions.

def connect_db():
    '''Connects to the sqlite database.'''

    DB_FILENAME = Path(__file__).parent/'inventory.db'
    db_already_exists = DB_FILENAME.exists()

    conn = sqlite3.connect(DB_FILENAME)
    db_was_just_created = not db_already_exists

    return conn, db_was_just_created


def initialize_data(conn):
    '''Initializes the inventory table with some data.'''
    cursor = conn.cursor()

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS entities (
            entity_uuid TEXT PRIMARY KEY,
            entity_type TEXT,
            mitam_id TEXT,
            deliverying_vessel_name TEXT,
            entity_inventory TEXT
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            entity_uuid TEXT FOREIGN KEY,
            transaction_type TEXT,
            transaction_location TEXT,
            user_id TEXT FOREIGN KEY
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            last_name TEXT,
            first_name TEXT,
            email TEXT,
            phone_number TEXT,
            organization TEXT,
            sponsor_first TEXT,
            sponsor_last TEXT,
            sponsor_email TEXT,
            sponsor_phone TEXT,
            user_type TEXT,
            password_hash TEXT
        )
        '''
    )
    conn.commit()


def load_data(conn):
    '''Loads the inventory data from the database.'''
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM entities')
        data = cursor.fetchall()
    except:
        return None

    df_entities = pd.DataFrame(data,
        columns=[
            'entity_uuid',
            'entity_type',
            'mitam_id',
            'deliverying_vessel_name',
            'entity_inventory'
        ])

    try:
        cursor.execute('SELECT * FROM transactions')
        data = cursor.fetchall()
    except:
        return None

    df_entities = pd.DataFrame(data,
        columns=[
            'transaction_id',
            'entity_uuid',
            'transaction_type',
            'transaction_location',
            'user_id'
        ])

    try:
        cursor.execute('SELECT * FROM users')
        data = cursor.fetchall()
    except:
        return None

    df_entities = pd.DataFrame(data,
        columns=[
            'user_id',
            'last_name',
            'first_name',
            'email',
            'phone_number',
            'organization',
            'sponsor_first',
            'sponsor_last',
            'sponsor_email',
            'sponsor_phone',
            'user_type',
            'password_hash'
        ])

    return df_entities, df_transactions, df_users


def update_data(conn, df, changes):
    '''Updates the inventory data in the database.'''
    cursor = conn.cursor()

    if changes['edited_rows']:
        deltas = st.session_state.inventory_table['edited_rows']
        rows = []

        for i, delta in deltas.items():
            row_dict = df.iloc[i].to_dict()
            row_dict.update(delta)
            rows.append(row_dict)

        cursor.executemany(
            '''
            UPDATE inventory
            SET
                item_name = :item_name,
                price = :price,
                units_sold = :units_sold,
                units_left = :units_left,
                cost_price = :cost_price,
                reorder_point = :reorder_point,
                description = :description
            WHERE id = :id
            ''',
            rows,
        )

    if changes['added_rows']:
        cursor.executemany(
            '''
            INSERT INTO inventory
                (id, item_name, price, units_sold, units_left, cost_price, reorder_point, description)
            VALUES
                (:id, :item_name, :price, :units_sold, :units_left, :cost_price, :reorder_point, :description)
            ''',
            (defaultdict(lambda: None, row) for row in changes['added_rows']),
        )

    if changes['deleted_rows']:
        cursor.executemany(
            'DELETE FROM inventory WHERE id = :id',
            ({'id': int(df.loc[i, 'id'])} for i in changes['deleted_rows'])
        )

    conn.commit()


# -----------------------------------------------------------------------------
# Draw the actual page, starting with the inventory table.

# Set the title that appears at the top of the page.
'''
# :shopping_bags: Inventory tracker

**Welcome to Alice's Corner Store's intentory tracker!**
This page reads and writes directly from/to our inventory database.
'''

st.info('''
    Use the table below to add, remove, and edit items.
    And don't forget to commit your changes when you're done.
    ''')

# Connect to database and create table if needed
conn, db_was_just_created = connect_db()

# Initialize data.
if db_was_just_created:
    initialize_data(conn)
    st.toast('Database initialized with some sample data.')

# Load data from database
df = load_data(conn)

# Display data with editable table
edited_df = st.data_editor(
    df,
    disabled=['id'], # Don't allow editing the 'id' column.
    num_rows='dynamic', # Allow appending/deleting rows.
    num_cols='dynamic', # TEST Allow appending/deleting columns.
    column_config={
        # Show dollar sign before price columns.
        "price": st.column_config.NumberColumn(format="$%.2f"),
        "cost_price": st.column_config.NumberColumn(format="$%.2f"),
    },
    key='inventory_table')

has_uncommitted_changes = any(len(v) for v in st.session_state.inventory_table.values())

st.button(
    'Commit changes',
    type='primary',
    disabled=not has_uncommitted_changes,
    # Update data in database
    on_click=update_data,
    args=(conn, df, st.session_state.inventory_table))


# -----------------------------------------------------------------------------
# Now some cool charts

# Add some space
''
''
''

st.subheader('Units left', divider='red')

need_to_reorder = df[df['units_left'] < df['reorder_point']].loc[:, 'item_name']

if len(need_to_reorder) > 0:
    items = '\n'.join(f'* {name}' for name in need_to_reorder)

    st.error(f"We're running dangerously low on the items below:\n {items}")

''
''

st.altair_chart(
    # Layer 1: Bar chart.
    alt.Chart(df)
        .mark_bar(
            orient='horizontal',
        )
        .encode(
            x='units_left',
            y='item_name',
        )
    # Layer 2: Chart showing the reorder point.
    + alt.Chart(df)
        .mark_point(
            shape='diamond',
            filled=True,
            size=50,
            color='salmon',
            opacity=1,
        )
        .encode(
            x='reorder_point',
            y='item_name',
        )
    ,
    use_container_width=True)

st.caption('NOTE: The :diamonds: location shows the reorder point.')

''
''
''

# -----------------------------------------------------------------------------

st.subheader('Best sellers', divider='orange')

''
''

st.altair_chart(alt.Chart(df)
    .mark_bar(orient='horizontal')
    .encode(
        x='units_sold',
        y=alt.Y('item_name').sort('-x'),
    ),
    use_container_width=True)
