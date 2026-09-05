# ruff: noqa: E501, I001
# Generated for issue #44 direct blocking Procedure prerequisites.

import django.db.models.deletion
from django.db import migrations, models


DEPENDENCY_GUARDS_SQL = r"""
DROP TRIGGER knowledge_document_type_preserved ON knowledge_documenttype;
DROP TRIGGER knowledge_authority_preserved ON knowledge_authority;
DROP TRIGGER knowledge_source_preserved ON knowledge_source;
DROP FUNCTION knowledge_guard_preserved_provenance();
DROP TRIGGER knowledge_evidence_source_guard ON knowledge_evidencelinksource;
DROP TRIGGER knowledge_evidence_guard ON knowledge_evidencelink;
DROP TRIGGER knowledge_basis_guard ON knowledge_eligibilitybasis;
DROP TRIGGER knowledge_fee_guard ON knowledge_fee;
DROP TRIGGER knowledge_warning_guard ON knowledge_warning;
DROP TRIGGER knowledge_step_guard ON knowledge_step;
DROP TRIGGER knowledge_checklist_guard ON knowledge_checklistitem;
DROP FUNCTION knowledge_guard_claim_child();
DROP FUNCTION knowledge_evidence_version(bigint);
DROP FUNCTION knowledge_claim_version(bigint,bigint,bigint,bigint,bigint);

CREATE FUNCTION knowledge_claim_version(item bigint, step bigint, warning bigint, fee bigint, basis bigint, dependency bigint) RETURNS bigint AS $$
 SELECT COALESCE((SELECT procedure_version_id FROM knowledge_checklistitem WHERE id=item),
                 (SELECT procedure_version_id FROM knowledge_step WHERE id=step),
                 (SELECT procedure_version_id FROM knowledge_warning WHERE id=warning),
                 (SELECT procedure_version_id FROM knowledge_fee WHERE id=fee),
                 (SELECT procedure_version_id FROM knowledge_eligibilitybasis WHERE id=basis),
                 (SELECT procedure_version_id FROM knowledge_proceduredependency WHERE id=dependency));
$$ LANGUAGE sql STABLE;
CREATE FUNCTION knowledge_evidence_version(link bigint) RETURNS bigint AS $$
 SELECT knowledge_claim_version(checklist_item_id, step_id, warning_id, fee_id, eligibility_basis_id, procedure_dependency_id)
 FROM knowledge_evidencelink WHERE id=link;
$$ LANGUAGE sql STABLE;
CREATE FUNCTION knowledge_guard_claim_child() RETURNS trigger AS $$
DECLARE old_version bigint; DECLARE new_version bigint; DECLARE old_state text; DECLARE new_state text;
BEGIN
 IF TG_TABLE_NAME IN ('knowledge_checklistitem','knowledge_step','knowledge_warning','knowledge_fee','knowledge_eligibilitybasis','knowledge_proceduredependency') THEN
   IF TG_OP <> 'INSERT' THEN old_version := OLD.procedure_version_id; END IF;
   IF TG_OP <> 'DELETE' THEN new_version := NEW.procedure_version_id; END IF;
 ELSIF TG_TABLE_NAME = 'knowledge_evidencelink' THEN
   IF TG_OP <> 'INSERT' THEN old_version := knowledge_claim_version(OLD.checklist_item_id, OLD.step_id, OLD.warning_id, OLD.fee_id, OLD.eligibility_basis_id, OLD.procedure_dependency_id); END IF;
   IF TG_OP <> 'DELETE' THEN new_version := knowledge_claim_version(NEW.checklist_item_id, NEW.step_id, NEW.warning_id, NEW.fee_id, NEW.eligibility_basis_id, NEW.procedure_dependency_id); END IF;
 ELSE
   IF TG_OP <> 'INSERT' THEN old_version := knowledge_evidence_version(OLD.evidence_link_id); END IF;
   IF TG_OP <> 'DELETE' THEN new_version := knowledge_evidence_version(NEW.evidence_link_id); END IF;
 END IF;
 SELECT state INTO old_state FROM knowledge_procedureversion WHERE id=old_version;
 SELECT state INTO new_state FROM knowledge_procedureversion WHERE id=new_version;
 IF old_state IN ('published','withdrawn') OR new_state IN ('published','withdrawn') THEN
   RAISE EXCEPTION 'published guidance aggregate is immutable';
 END IF;
 RETURN COALESCE(NEW, OLD);
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER knowledge_checklist_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_checklistitem FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_step_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_step FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_warning_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_warning FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_fee_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_fee FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_basis_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_eligibilitybasis FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_dependency_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_proceduredependency FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_evidencelink FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_evidence_source_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_evidencelinksource FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();

CREATE FUNCTION knowledge_guard_preserved_provenance() RETURNS trigger AS $$
DECLARE is_used boolean;
BEGIN
 IF TG_TABLE_NAME = 'knowledge_documenttype' THEN
  SELECT EXISTS(SELECT 1 FROM knowledge_checklistitem c JOIN knowledge_procedureversion pv ON pv.id=c.procedure_version_id WHERE c.document_type_id=OLD.id AND pv.state IN ('published','withdrawn')) INTO is_used;
 ELSIF TG_TABLE_NAME = 'knowledge_source' THEN
  SELECT EXISTS(SELECT 1 FROM knowledge_evidencelinksource es JOIN knowledge_evidencelink e ON e.id=es.evidence_link_id JOIN knowledge_procedureversion pv ON pv.id=knowledge_claim_version(e.checklist_item_id,e.step_id,e.warning_id,e.fee_id,e.eligibility_basis_id,e.procedure_dependency_id) WHERE es.source_id=OLD.id AND pv.state IN ('published','withdrawn')) INTO is_used;
 ELSE
  SELECT EXISTS(SELECT 1 FROM knowledge_source s JOIN knowledge_evidencelinksource es ON es.source_id=s.id JOIN knowledge_evidencelink e ON e.id=es.evidence_link_id JOIN knowledge_procedureversion pv ON pv.id=knowledge_claim_version(e.checklist_item_id,e.step_id,e.warning_id,e.fee_id,e.eligibility_basis_id,e.procedure_dependency_id) WHERE s.authority_id=OLD.id AND pv.state IN ('published','withdrawn')) INTO is_used;
 END IF;
 IF is_used THEN RAISE EXCEPTION 'published provenance identity is immutable'; END IF;
 RETURN COALESCE(NEW, OLD);
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER knowledge_source_preserved BEFORE UPDATE OR DELETE ON knowledge_source FOR EACH ROW EXECUTE FUNCTION knowledge_guard_preserved_provenance();
CREATE TRIGGER knowledge_authority_preserved BEFORE UPDATE OR DELETE ON knowledge_authority FOR EACH ROW EXECUTE FUNCTION knowledge_guard_preserved_provenance();
CREATE TRIGGER knowledge_document_type_preserved BEFORE UPDATE OR DELETE ON knowledge_documenttype FOR EACH ROW EXECUTE FUNCTION knowledge_guard_preserved_provenance();
"""


DEPENDENCY_GUARDS_REVERSE_SQL = r"""
DELETE FROM knowledge_evidencelinksource WHERE evidence_link_id IN (SELECT id FROM knowledge_evidencelink WHERE procedure_dependency_id IS NOT NULL);
DELETE FROM knowledge_evidencelink WHERE procedure_dependency_id IS NOT NULL;
DROP TRIGGER knowledge_document_type_preserved ON knowledge_documenttype;
DROP TRIGGER knowledge_authority_preserved ON knowledge_authority;
DROP TRIGGER knowledge_source_preserved ON knowledge_source;
DROP FUNCTION knowledge_guard_preserved_provenance();
DROP TRIGGER knowledge_evidence_source_guard ON knowledge_evidencelinksource;
DROP TRIGGER knowledge_evidence_guard ON knowledge_evidencelink;
DROP TRIGGER knowledge_dependency_guard ON knowledge_proceduredependency;
DROP TRIGGER knowledge_basis_guard ON knowledge_eligibilitybasis;
DROP TRIGGER knowledge_fee_guard ON knowledge_fee;
DROP TRIGGER knowledge_warning_guard ON knowledge_warning;
DROP TRIGGER knowledge_step_guard ON knowledge_step;
DROP TRIGGER knowledge_checklist_guard ON knowledge_checklistitem;
DROP FUNCTION knowledge_guard_claim_child();
DROP FUNCTION knowledge_evidence_version(bigint);
DROP FUNCTION knowledge_claim_version(bigint,bigint,bigint,bigint,bigint,bigint);

CREATE FUNCTION knowledge_claim_version(item bigint, step bigint, warning bigint, fee bigint, basis bigint) RETURNS bigint AS $$
 SELECT COALESCE((SELECT procedure_version_id FROM knowledge_checklistitem WHERE id=item),
                 (SELECT procedure_version_id FROM knowledge_step WHERE id=step),
                 (SELECT procedure_version_id FROM knowledge_warning WHERE id=warning),
                 (SELECT procedure_version_id FROM knowledge_fee WHERE id=fee),
                 (SELECT procedure_version_id FROM knowledge_eligibilitybasis WHERE id=basis));
$$ LANGUAGE sql STABLE;
CREATE FUNCTION knowledge_evidence_version(link bigint) RETURNS bigint AS $$
 SELECT knowledge_claim_version(checklist_item_id, step_id, warning_id, fee_id, eligibility_basis_id)
 FROM knowledge_evidencelink WHERE id=link;
$$ LANGUAGE sql STABLE;
CREATE FUNCTION knowledge_guard_claim_child() RETURNS trigger AS $$
DECLARE old_version bigint; DECLARE new_version bigint; DECLARE old_state text; DECLARE new_state text;
BEGIN
 IF TG_TABLE_NAME IN ('knowledge_checklistitem','knowledge_step','knowledge_warning','knowledge_fee','knowledge_eligibilitybasis') THEN
   IF TG_OP <> 'INSERT' THEN old_version := OLD.procedure_version_id; END IF;
   IF TG_OP <> 'DELETE' THEN new_version := NEW.procedure_version_id; END IF;
 ELSIF TG_TABLE_NAME = 'knowledge_evidencelink' THEN
   IF TG_OP <> 'INSERT' THEN old_version := knowledge_claim_version(OLD.checklist_item_id, OLD.step_id, OLD.warning_id, OLD.fee_id, OLD.eligibility_basis_id); END IF;
   IF TG_OP <> 'DELETE' THEN new_version := knowledge_claim_version(NEW.checklist_item_id, NEW.step_id, NEW.warning_id, NEW.fee_id, NEW.eligibility_basis_id); END IF;
 ELSE
   IF TG_OP <> 'INSERT' THEN old_version := knowledge_evidence_version(OLD.evidence_link_id); END IF;
   IF TG_OP <> 'DELETE' THEN new_version := knowledge_evidence_version(NEW.evidence_link_id); END IF;
 END IF;
 SELECT state INTO old_state FROM knowledge_procedureversion WHERE id=old_version;
 SELECT state INTO new_state FROM knowledge_procedureversion WHERE id=new_version;
 IF old_state IN ('published','withdrawn') OR new_state IN ('published','withdrawn') THEN
   RAISE EXCEPTION 'published guidance aggregate is immutable';
 END IF;
 RETURN COALESCE(NEW, OLD);
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER knowledge_checklist_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_checklistitem FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_step_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_step FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_warning_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_warning FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_fee_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_fee FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_basis_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_eligibilitybasis FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_evidencelink FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();
CREATE TRIGGER knowledge_evidence_source_guard BEFORE INSERT OR UPDATE OR DELETE ON knowledge_evidencelinksource FOR EACH ROW EXECUTE FUNCTION knowledge_guard_claim_child();

CREATE FUNCTION knowledge_guard_preserved_provenance() RETURNS trigger AS $$
DECLARE is_used boolean;
BEGIN
 IF TG_TABLE_NAME = 'knowledge_documenttype' THEN
  SELECT EXISTS(SELECT 1 FROM knowledge_checklistitem c JOIN knowledge_procedureversion pv ON pv.id=c.procedure_version_id WHERE c.document_type_id=OLD.id AND pv.state IN ('published','withdrawn')) INTO is_used;
 ELSIF TG_TABLE_NAME = 'knowledge_source' THEN
  SELECT EXISTS(SELECT 1 FROM knowledge_evidencelinksource es JOIN knowledge_evidencelink e ON e.id=es.evidence_link_id JOIN knowledge_procedureversion pv ON pv.id=knowledge_claim_version(e.checklist_item_id,e.step_id,e.warning_id,e.fee_id,e.eligibility_basis_id) WHERE es.source_id=OLD.id AND pv.state IN ('published','withdrawn')) INTO is_used;
 ELSE
  SELECT EXISTS(SELECT 1 FROM knowledge_source s JOIN knowledge_evidencelinksource es ON es.source_id=s.id JOIN knowledge_evidencelink e ON e.id=es.evidence_link_id JOIN knowledge_procedureversion pv ON pv.id=knowledge_claim_version(e.checklist_item_id,e.step_id,e.warning_id,e.fee_id,e.eligibility_basis_id) WHERE s.authority_id=OLD.id AND pv.state IN ('published','withdrawn')) INTO is_used;
 END IF;
 IF is_used THEN RAISE EXCEPTION 'published provenance identity is immutable'; END IF;
 RETURN COALESCE(NEW, OLD);
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER knowledge_source_preserved BEFORE UPDATE OR DELETE ON knowledge_source FOR EACH ROW EXECUTE FUNCTION knowledge_guard_preserved_provenance();
CREATE TRIGGER knowledge_authority_preserved BEFORE UPDATE OR DELETE ON knowledge_authority FOR EACH ROW EXECUTE FUNCTION knowledge_guard_preserved_provenance();
CREATE TRIGGER knowledge_document_type_preserved BEFORE UPDATE OR DELETE ON knowledge_documenttype FOR EACH ROW EXECUTE FUNCTION knowledge_guard_preserved_provenance();
"""


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0007_eligibility_basis_evaluation")]

    operations = [
        migrations.CreateModel(
            name="ProcedureDependency",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("semantic_id", models.CharField(max_length=128)),
                ("text_ar", models.TextField()),
                ("text_en", models.TextField()),
                (
                    "relation",
                    models.CharField(
                        choices=[
                            ("blocking_prerequisite", "Blocking prerequisite"),
                        ],
                        default="blocking_prerequisite",
                        max_length=32,
                    ),
                ),
                ("applicability", models.JSONField(blank=True, default=dict)),
                ("satisfied_when", models.JSONField(blank=True, default=dict)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("effective_from", models.DateField(blank=True, null=True)),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("verified_on", models.DateField(blank=True, null=True)),
                ("reverify_on", models.DateField(blank=True, null=True)),
                (
                    "verification_state",
                    models.CharField(
                        choices=[
                            ("current", "Current"),
                            ("needs_reverification", "Needs reverification"),
                            ("stale", "Stale"),
                            ("disputed", "Disputed"),
                            ("unknown", "Unknown"),
                        ],
                        default="unknown",
                        max_length=24,
                    ),
                ),
                (
                    "procedure_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dependencies",
                        to="knowledge.procedureversion",
                    ),
                ),
                (
                    "target_procedure",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="incoming_dependencies",
                        to="knowledge.procedure",
                    ),
                ),
            ],
            options={
                "ordering": ("procedure_version_id", "display_order", "semantic_id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("procedure_version", "semantic_id"),
                        name="unique_dependency_id_per_version",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(semantic_id__regex=r".*[^[:space:]].*"),
                        name="dependency_id_nonblank",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(text_ar__regex=r".*[^[:space:]].*"),
                        name="dependency_ar_nonblank",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(text_en__regex=r".*[^[:space:]].*"),
                        name="dependency_en_nonblank",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(relation="blocking_prerequisite"),
                        name="dependency_relation_supported",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(effective_from__isnull=True)
                        | models.Q(effective_to__isnull=True)
                        | models.Q(effective_from__lte=models.F("effective_to")),
                        name="dependency_dates_ordered",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            verification_state__in=[
                                "current",
                                "needs_reverification",
                                "stale",
                                "disputed",
                                "unknown",
                            ]
                        ),
                        name="dependency_verification_supported",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="evidencelink",
            name="procedure_dependency",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="evidence_links",
                to="knowledge.proceduredependency",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="evidencelink",
            name="evidence_exactly_one_owner",
        ),
        migrations.AddConstraint(
            model_name="evidencelink",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        checklist_item__isnull=False,
                        step__isnull=True,
                        warning__isnull=True,
                        fee__isnull=True,
                        eligibility_basis__isnull=True,
                        procedure_dependency__isnull=True,
                    )
                    | models.Q(
                        checklist_item__isnull=True,
                        step__isnull=False,
                        warning__isnull=True,
                        fee__isnull=True,
                        eligibility_basis__isnull=True,
                        procedure_dependency__isnull=True,
                    )
                    | models.Q(
                        checklist_item__isnull=True,
                        step__isnull=True,
                        warning__isnull=False,
                        fee__isnull=True,
                        eligibility_basis__isnull=True,
                        procedure_dependency__isnull=True,
                    )
                    | models.Q(
                        checklist_item__isnull=True,
                        step__isnull=True,
                        warning__isnull=True,
                        fee__isnull=False,
                        eligibility_basis__isnull=True,
                        procedure_dependency__isnull=True,
                    )
                    | models.Q(
                        checklist_item__isnull=True,
                        step__isnull=True,
                        warning__isnull=True,
                        fee__isnull=True,
                        eligibility_basis__isnull=False,
                        procedure_dependency__isnull=True,
                    )
                    | models.Q(
                        checklist_item__isnull=True,
                        step__isnull=True,
                        warning__isnull=True,
                        fee__isnull=True,
                        eligibility_basis__isnull=True,
                        procedure_dependency__isnull=False,
                    )
                ),
                name="evidence_exactly_one_owner",
            ),
        ),
        migrations.RunSQL(
            DEPENDENCY_GUARDS_SQL,
            reverse_sql=DEPENDENCY_GUARDS_REVERSE_SQL,
        ),
    ]
