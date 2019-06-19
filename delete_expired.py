import os
from datetime import datetime

import db


if __name__ == '__main__':
    files = db.session.query(db.File).filter(db.File.expires <= datetime.utcnow())
    for f in files:
        try:
            db.session.delete(f)
            db.session.commit()
            os.remove(os.path.join('uploads/', f.filename))
        except OSError:
            pass
