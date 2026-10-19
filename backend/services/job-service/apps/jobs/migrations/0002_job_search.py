# Search support for the Job Service (ARCHITECTURE.md section 7).
#
# `search_vector` cannot be a GENERATED column: `array_to_string` is only
# STABLE, so PostgreSQL rejects it in a generation expression. A BEFORE
# INSERT OR UPDATE trigger maintains it instead. Weights: title (A) beats
# skills/company (B) beats description (C).
#
# The trigger is created BEFORE the indexes so the backfill UPDATE fills every
# existing row first and the GIN index is built once, on final values.

import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models

SEARCH_SQL = """
CREATE OR REPLACE FUNCTION jobs_search_vector_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A')
     || setweight(to_tsvector('english', coalesce(array_to_string(NEW.skills, ' '), '')), 'B')
     || setweight(to_tsvector('english', coalesce(NEW.company, '')), 'B')
     || setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C');
    RETURN NEW;
END
$$;

CREATE TRIGGER jobs_search_vector_trg
BEFORE INSERT OR UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION jobs_search_vector_update();

-- Setting the column to NULL fires the trigger, which computes the real value.
-- The expression therefore lives in exactly one place.
UPDATE jobs SET search_vector = NULL;
"""

SEARCH_SQL_REVERSE = """
DROP TRIGGER IF EXISTS jobs_search_vector_trg ON jobs;
DROP FUNCTION IF EXISTS jobs_search_vector_update();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='search_vector',
            field=django.contrib.postgres.search.SearchVectorField(editable=False, null=True),
        ),
        migrations.RunSQL(sql=SEARCH_SQL, reverse_sql=SEARCH_SQL_REVERSE),
        migrations.AddIndex(
            model_name='job',
            index=django.contrib.postgres.indexes.GinIndex(condition=models.Q(('status', 'PUBLISHED')), fields=['search_vector'], name='jobs_search_vector_gin'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=django.contrib.postgres.indexes.GinIndex(fields=['skills'], name='jobs_skills_gin'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(condition=models.Q(('status', 'PUBLISHED')), fields=['-published_at', 'id'], name='jobs_pub_browse_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['employment_type'], name='jobs_employment_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(django.db.models.functions.text.Lower('location'), name='jobs_location_lower_idx'),
        ),
    ]
