profilesCreate = """
CREATE TABLE IF NOT EXISTS profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	username VARCHAR NOT NULL,
	PRIMARY KEY (id)
)
"""

modelsCreate = """
CREATE TABLE IF NOT EXISTS models (
	id INTEGER NOT NULL,
	model_id INTEGER NOT NULL,
	UNIQUE (model_id)
	PRIMARY KEY (id)
)
"""

storiesCreate = """
CREATE TABLE IF NOT EXISTS stories (
	id INTEGER NOT NULL, 
	post_id INTEGER NOT NULL, 
	text VARCHAR, 
	price INTEGER, 
	paid INTEGER, 
	archived BOOLEAN, 
	created_at TIMESTAMP, 
    model_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (post_id,model_id)
)
"""


postNormalCheck = """
SELECT post_id FROM posts where archived=False
"""


storiesInsert = f"""INSERT INTO 'stories'(
post_id, text,price,paid,archived,created_at,model_id)
            VALUES (?, ?,?,?,?,?,?);"""


storiesUpdate = f"""UPDATE stories
SET text = ?, price = ?, paid = ?, archived = ?, created_at = ? ,model_id=?
WHERE post_id = ?;"""


storiesAddColumnID = """
ALTER TABLE stories ADD COLUMN model_id INTEGER;
"""


storiesALLTransition = """
select post_id,text,price,paid,archived,created_at from stories
"""


allPOSTCheck = """
SELECT post_id FROM posts
"""


allStoriesCheck = """
SELECT post_id FROM stories
"""

storiesDrop = """
drop table stories;
"""


profileDupeCheck = """
SELECT * FROM profiles where user_id=(?)
"""
profileTableCheck = """
SELECT name FROM sqlite_master WHERE type='table' AND name='profiles';
"""

profileInsert = f"""INSERT INTO 'profiles'(
user_id,username)
            VALUES (?, ?);"""

profileUpdate = f"""Update 'profiles'
SET
user_id=?,username=?
WHERE user_id=(?);"""


modelDupeCheck = """
SELECT * FROM models where model_id=(?)
"""

modelInsert = f"""
INSERT INTO models (model_id)
VALUES (?);
"""


profilesALL = """
select user_id,username from profiles
"""
profilesDrop = """
DROP TABLE profiles;
"""
