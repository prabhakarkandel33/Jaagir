# Search support for the Candidate Service replica (ARCHITECTURE.md section 7).
#
# Identical design to the Job Service migration, kept as a copy because each
# service owns its database and shared runtime code is limited to
# `packages/contracts` (invariant I1). The trigger also fires on the consumer's
# version-guarded upsert, so the replica stays searchable with no extra code.

import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.functions.text
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
UPDATE jobs SET search_vector = NULL;
"""

SEARCH_SQL_REVERSE = """
DROP TRIGGER IF EXISTS jobs_search_vector_trg ON jobs;
DROP FUNCTION IF EXISTS jobs_search_vector_update();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0001_initial'),
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
            index=django.contrib.postgres.indexes.GinIndex(condition=models.Q(('status', 'PUBLISHED')), fields=['search_vector'], name='cjobs_search_vector_gin'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=django.contrib.postgres.indexes.GinIndex(fields=['skills'], name='cjobs_skills_gin'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(condition=models.Q(('status', 'PUBLISHED')), fields=['-published_at', 'id'], name='cjobs_pub_browse_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(fields=['employment_type'], name='cjobs_employment_idx'),
        ),
        migrations.AddIndex(
            model_name='job',
            index=models.Index(django.db.models.functions.text.Lower('location'), name='cjobs_location_lower_idx'),
        ),
    ]
