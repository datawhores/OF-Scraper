mediaCreate= """
CREATE TABLE IF NOT EXISTS medias (
	id INTEGER NOT NULL, 
	media_id INTEGER, 
	post_id INTEGER NOT NULL, 
	link VARCHAR, 
	directory VARCHAR, 
	filename VARCHAR, 
	size INTEGER, 
	api_type VARCHAR, 
	media_type VARCHAR, 
	preview INTEGER, 
	linked VARCHAR, 
	downloaded INTEGER, 
	created_at TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (media_id)
);"""

messagesCreate="""
CREATE TABLE IF NOT EXISTS messages (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP, 
	user_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (post_id)
)
"""
postCreate=\
"""
CREATE TABLE IF NOT EXISTS posts (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (post_id)
)
"""
otherCreate=\
"""
CREATE TABLE IF NOT EXISTS others (
	id INTEGER NOT NULL,  
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (post_id)
)
"""
productCreate=\
"""
CREATE TABLE IF NOT EXISTS products (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP, title VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (post_id)
)
"""
profilesCreate=\
"""
CREATE TABLE IF NOT EXISTS profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	username VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
)
"""

storiesCreate="""
CREATE TABLE IF NOT EXISTS stories (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (post_id)
)
"""

messagesInsert=\
f"""INSERT INTO 'messages'(
post_id, text,price,paid,archived,
created_at,user_id)
            VALUES (?, ?,?,?,?,?,?);"""

messageDupeCheck=\
"""
SELECT * FROM messages where post_id=(?)
"""



postInsert=\
f"""INSERT INTO 'posts'(
post_id, text,price,paid,archived,
created_at)
            VALUES (?, ?,?,?,?,?);"""

postDupeCheck=\
"""
SELECT * FROM posts where post_id=(?)
"""


storiesInsert=\
f"""INSERT INTO 'stories'(
post_id, text,price,paid,archived,
created_at)
            VALUES (?, ?,?,?,?,?);"""

storiesDupeCheck=\
"""
SELECT * FROM stories where post_id=(?)
"""



