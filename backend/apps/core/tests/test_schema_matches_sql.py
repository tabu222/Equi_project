"""
Test chạy trên SQLite không bắt được lỗi gõ sai tên bảng / tên cột so với SQL Server.
Test này đọc sql/horse_v2.sql và so với khai báo model, để chắc chắn mọi model khớp database thật.
"""
import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

from apps.core import flows

SQL = Path(settings.SQL_SCRIPT).read_text(encoding="utf-8")
SQL_TYPES = {"INT", "BIGINT", "BIT", "VARCHAR", "NVARCHAR", "DATE", "DATETIME2", "TIME", "DECIMAL", "AS"}


def sql_tables():
    tables = {}
    for match in re.finditer(r"CREATE TABLE dbo\.\[?(\w+)\]?\s*\((.*?)\n\);", SQL, re.S):
        name, body = match.group(1), match.group(2)
        columns = {}
        for line in body.splitlines():
            line = line.strip()
            m = re.match(r"(\w+)\s+(\w+)", line)
            if not m or m.group(2).upper() not in SQL_TYPES:
                continue
            columns[m.group(1)] = "NOT NULL" in line.upper() or "PRIMARY KEY" in line.upper()
        tables[name] = columns
    return tables


def business_models():
    return [m for m in apps.get_models() if m.__module__.startswith("apps.")]


class SchemaMatchesSqlTests(SimpleTestCase):
    def test_every_table_has_a_model(self):
        modelled = {m._meta.db_table for m in business_models()}
        # SQL mô tả đủ 4 flow; backend được nộp dần nên chỉ đòi model của các flow đã có.
        flow_tables = {
            "Flow 2": (flows.has_training, {
                "Specialization", "TrainerSpecialization", "TrainerProfile", "TrainerCredential", "TrainerRaceResult",
                "HorseAssessment", "TrainerHorseAssignment", "HorseWorkRiderPreference", "TrainingPlan",
                "TrainingPlanStage", "TrainingSession", "TrainingResult", "TrainingReview"}),
            "Flow 3": (flows.has_flow3, {
                "TrainingLock", "Treatment", "Vaccination", "MedicalSchedule", "HealthReport", "HealthReportNote"}),
            "Flow 4": (flows.has_care, {
                "DietPlan", "DietMeal", "CareTask", "InventoryItem", "InventoryRequest", "InventoryRequestItem"}),
        }
        not_delivered = set().union(*(tables for installed, tables in flow_tables.values() if not installed()))
        self.assertEqual(set(sql_tables()) - modelled, not_delivered, "Thiếu model của flow đã có")

    def test_model_columns_exist_in_sql(self):
        tables = sql_tables()
        problems = []
        for model in business_models():
            table = model._meta.db_table
            if table not in tables:
                problems.append(f"{model.__name__}: không có bảng {table} trong SQL")
                continue
            for field in model._meta.concrete_fields:
                if field.column is None:          # khóa chính ghép (CompositePrimaryKey)
                    continue
                if field.column not in tables[table]:
                    problems.append(f"{table}.{field.column} không có trong SQL")
                elif tables[table][field.column] and field.null:
                    problems.append(f"{table}.{field.column}: SQL là NOT NULL nhưng model cho phép null")
        self.assertEqual(problems, [])

    def test_sql_not_null_columns_are_written(self):
        """Cột NOT NULL không có DEFAULT trong SQL phải có field tương ứng, nếu không lệnh INSERT sẽ lỗi."""
        tables = sql_tables()
        computed = {("Horse", "SexClass")}
        for model in business_models():
            table = model._meta.db_table
            model_columns = {f.column for f in model._meta.concrete_fields if f.column}
            for column, not_null in tables.get(table, {}).items():
                if (table, column) in computed:
                    continue
                with self.subTest(table=table, column=column):
                    self.assertIn(column, model_columns, f"{table}.{column} chưa khai báo trong model")


def sql_check_values():
    """{(bảng, cột): {giá trị trong CHECK ... IN (...)}}"""
    values = {}
    for match in re.finditer(r"CREATE TABLE dbo\.\[?(\w+)\]?\s*\((.*?)\n\);", SQL, re.S):
        table, body = match.group(1), match.group(2)
        for column, items in re.findall(r"(\w+)\s+IN\s*\(([^)]*)\)", body):
            values.setdefault((table, column), set()).update(re.findall(r"'([^']*)'", items))
    return values


class ChoicesMatchSqlChecks(SimpleTestCase):
    def test_choices_equal_check_constraints(self):
        """Giá trị trạng thái trong code phải đúng y như CHECK trong SQL (sai một chữ là SQL Server từ chối)."""
        checks = sql_check_values()
        problems = []
        for model in business_models():
            for field in model._meta.concrete_fields:
                key = (model._meta.db_table, field.column)
                if field.choices and key in checks:
                    code_values = {value for value, _ in field.choices}
                    if code_values != checks[key]:
                        problems.append(f"{key}: code {sorted(code_values)} != SQL {sorted(checks[key])}")
                elif key in checks and not field.choices:
                    problems.append(f"{key}: SQL có CHECK nhưng model chưa khai báo choices")
        self.assertEqual(problems, [])
