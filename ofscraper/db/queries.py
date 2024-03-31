

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



