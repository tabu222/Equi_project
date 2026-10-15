"""Flow 4: khẩu phần (Head Trainer lập, Vet duyệt), việc chăm sóc của Groom, kho vật tư."""
from datetime import timedelta

from apps.care.models import CareTask, DietPlan, InventoryItem

from .test_training import TODAY, TrainingTestCase

MEALS = [
    {"MealTime": "06:00", "FeedType": "Yến mạch", "Quantity": 3, "Unit": "kg"},
    {"MealTime": "17:00", "FeedType": "Cỏ khô", "Quantity": 6.5, "Unit": "kg", "Note": "Ngâm nước"},
]


class DietTests(TrainingTestCase):
    def create_plan(self, horse_id, start=None):
        res = self.client_for(self.head).post(f"/api/horses/{horse_id}/diet-plans", {
            "DietDescription": "Khẩu phần giai đoạn tăng tốc", "StartDate": (start or TODAY).isoformat(),
            "Meals": MEALS}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        return res.data

    def test_diet_flow(self):
        horse_id = self.approved_horse()
        head, vet = self.client_for(self.head), self.client_for(self.vet)
        self.assertEqual(self.client_for(self.vet).post(f"/api/horses/{horse_id}/diet-plans", {
            "StartDate": TODAY.isoformat(), "Meals": MEALS}, format="json").status_code, 403)
        res = head.post(f"/api/horses/{horse_id}/diet-plans", {"StartDate": TODAY.isoformat(), "Meals": []},
                        format="json")
        self.assertIn("Meals", res.data)

        plan = self.create_plan(horse_id)
        plan_id = plan["DietPlanID"]
        self.assertEqual(plan["Status"], "Pending")
        self.assertEqual(len(plan["Meals"]), 2)
        self.assertEqual(plan["Meals"][1]["Quantity"], 6.5)
        self.assertEqual(head.post(f"/api/diet-plans/{plan_id}/approve", {}, format="json").status_code, 403)
        self.assertEqual([p["DietPlanID"] for p in vet.get("/api/diet-plans?Status=Pending").data], [plan_id])

        res = vet.post(f"/api/diet-plans/{plan_id}/reject", {}, format="json")
        self.assertIn("VetNote", res.data)
        res = vet.post(f"/api/diet-plans/{plan_id}/reject", {"VetNote": "Giảm yến mạch vì đang dùng thuốc"},
                       format="json")
        self.assertEqual(res.data["Status"], "Rejected")
        res = head.patch(f"/api/diet-plans/{plan_id}", {"Meals": [
            {"MealTime": "06:00", "FeedType": "Yến mạch", "Quantity": 2, "Unit": "kg"}]}, format="json")
        self.assertEqual(res.data["Status"], "Pending")
        self.assertEqual(len(res.data["Meals"]), 1)
        res = vet.post(f"/api/diet-plans/{plan_id}/approve", {"VetNote": "OK"}, format="json")
        self.assertEqual(res.data["Status"], "Approved")
        self.assertEqual(res.data["ReviewedByVetID"], self.vet.id)
        self.assertEqual(self.client_for(self.groom).get(f"/api/horses/{horse_id}/current-diet").data["DietPlanID"],
                         plan_id)

        # Khẩu phần mới được duyệt -> khẩu phần cũ Expired
        new_id = self.create_plan(horse_id)["DietPlanID"]
        vet.post(f"/api/diet-plans/{new_id}/approve", {}, format="json")
        self.assertEqual(DietPlan.objects.get(pk=plan_id).status, "Expired")
        res = vet.post(f"/api/diet-plans/{new_id}/adjust", {"VetNote": "Thêm điện giải", "Meals": MEALS},
                       format="json")
        self.assertEqual(res.data["Status"], "Adjusted")
        self.assertEqual(head.get(f"/api/horses/{horse_id}/current-diet").data["DietPlanID"], new_id)
        self.assertEqual(head.patch(f"/api/diet-plans/{new_id}", {"DietDescription": "x"}, format="json")
                         .data["code"], "INVALID_STATUS")


class CareTaskTests(TrainingTestCase):
    def test_care_tasks(self):
        horse_id = self.approved_horse()
        head, groom = self.client_for(self.head), self.client_for(self.groom)
        at = f"{TODAY.isoformat()}T15:00:00"
        res = head.post("/api/care-tasks", {"HorseID": horse_id, "TaskType": "Ice Leg Soak", "ScheduledAt": at},
                        format="json")
        self.assertIn("GroomID", res.data)
        res = head.post("/api/care-tasks", {"HorseID": horse_id, "GroomID": self.groom.id,
                                            "TaskType": "Ice Leg Soak", "ScheduledAt": at, "Note": "20 phút"},
                        format="json")
        self.assertEqual(res.status_code, 201, res.data)
        task_id = res.data["CareTaskID"]
        self.assertEqual(res.data["AssignedBy"], self.head.id)

        # Groom tự tạo việc cho mình
        res = groom.post("/api/care-tasks", {"HorseID": horse_id, "TaskType": "Cleaning", "ScheduledAt": at},
                         format="json")
        self.assertEqual(res.data["GroomID"], self.groom.id)
        self.assertIsNone(res.data["AssignedBy"])
        own_id = res.data["CareTaskID"]

        mine = groom.get(f"/api/care-tasks?mine=1&Date={TODAY.isoformat()}").data
        self.assertEqual({t["CareTaskID"] for t in mine}, {task_id, own_id})
        self.assertIn(("CARE_TASK", task_id), {(n["Type"], n["EntityID"]) for n in groom.get("/api/notifications").data})

        self.assertEqual(groom.patch(f"/api/care-tasks/{task_id}", {"GroomID": self.groom.id}, format="json")
                         .data["code"], "NOT_TASK_OWNER")
        self.assertEqual(head.post(f"/api/care-tasks/{task_id}/complete").data["code"], "NOT_TASK_GROOM")
        res = groom.post(f"/api/care-tasks/{task_id}/complete", {"Note": "Xong"}, format="json")
        self.assertEqual(res.data["Status"], "Completed")
        self.assertIsNotNone(res.data["CompletedAt"])
        self.assertEqual(groom.post(f"/api/care-tasks/{own_id}/skip", {}, format="json").status_code, 400)
        self.assertEqual(groom.post(f"/api/care-tasks/{own_id}/skip", {"Reason": "Ngựa đi khám"}, format="json")
                         .data["Status"], "Skipped")
        self.assertEqual(self.client_for(self.rider).post("/api/care-tasks", {}, format="json").status_code, 403)

    def test_archive_skips_pending_tasks(self):
        horse_id = self.approved_horse()
        res = self.client_for(self.groom).post("/api/care-tasks", {
            "HorseID": horse_id, "TaskType": "Feeding",
            "ScheduledAt": f"{(TODAY + timedelta(days=1)).isoformat()}T06:00:00"}, format="json")
        self.client_for(self.manager).post(f"/api/horses/{horse_id}/archive", {"Reason": "Rời CLB"}, format="json")
        self.assertEqual(CareTask.objects.get(pk=res.data["CareTaskID"]).status, "Skipped")


class InventoryTests(TrainingTestCase):
    def test_inventory_flow(self):
        manager, groom = self.client_for(self.manager), self.client_for(self.groom)
        res = manager.post("/api/inventory-items", {"ItemName": "Cám viên", "ItemType": "Food", "Unit": "kg",
                                                    "Quantity": 100, "MinimumQuantity": 30}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["Status"], "Available")
        feed = res.data["InventoryItemID"]
        bandage = manager.post("/api/inventory-items", {"ItemName": "Băng chân", "ItemType": "Care Equipment",
                                                        "Unit": "cuộn", "Quantity": 5}, format="json").data
        self.assertEqual(groom.post("/api/inventory-items", {}, format="json").status_code, 403)
        self.assertEqual(len(groom.get("/api/inventory-items").data), 2)

        res = groom.post("/api/inventory-requests", {"Reason": "Hết cám buổi chiều", "Items": [
            {"InventoryItemID": feed, "RequestedQuantity": 80},
            {"InventoryItemID": bandage["InventoryItemID"], "RequestedQuantity": 10}]}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        req_id = res.data["InventoryRequestID"]
        self.assertIn(("INVENTORY_REQUEST", req_id),
                      {(n["Type"], n["EntityID"]) for n in manager.get("/api/notifications").data})

        res = manager.post(f"/api/inventory-requests/{req_id}/approve", {}, format="json")
        self.assertEqual(res.data["code"], "INSUFFICIENT_STOCK")        # băng chân chỉ còn 5
        res = manager.post(f"/api/inventory-requests/{req_id}/approve", {"Items": [
            {"InventoryItemID": bandage["InventoryItemID"], "ApprovedQuantity": 5}]}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["Status"], "Approved")
        self.assertEqual({i["InventoryItemID"]: i["ApprovedQuantity"] for i in res.data["Items"]},
                         {feed: 80, bandage["InventoryItemID"]: 5})
        self.assertEqual(InventoryItem.objects.get(pk=feed).status, "Low Stock")              # còn 20 <= 30
        self.assertEqual(InventoryItem.objects.get(pk=bandage["InventoryItemID"]).status, "Out of Stock")
        self.assertIn("LOW_STOCK", {n["Type"] for n in manager.get("/api/notifications").data})

        res = manager.post(f"/api/inventory-items/{feed}/stock", {"Change": 200, "Note": "Nhập kho"}, format="json")
        self.assertEqual(res.data["Quantity"], 220)
        self.assertEqual(res.data["Status"], "Available")
        self.assertEqual(manager.post(f"/api/inventory-items/{feed}/stock", {"Change": -500}, format="json")
                         .data["code"], "INSUFFICIENT_STOCK")

        # Từ chối, hủy
        res = groom.post("/api/inventory-requests", {"Items": [{"InventoryItemID": feed, "RequestedQuantity": 5}]},
                         format="json")
        second = res.data["InventoryRequestID"]
        res = manager.post(f"/api/inventory-requests/{second}/reject", {"Note": "Đã cấp hôm qua"}, format="json")
        self.assertEqual(res.data["RejectNote"], "Đã cấp hôm qua")
        third = groom.post("/api/inventory-requests", {"Items": [{"InventoryItemID": feed, "RequestedQuantity": 5}]},
                           format="json").data["InventoryRequestID"]
        self.assertEqual(self.client_for(self.head).post(f"/api/inventory-requests/{third}/cancel").status_code, 404)
        self.assertEqual(groom.post(f"/api/inventory-requests/{third}/cancel").data["Status"], "Cancelled")
        self.assertEqual(len(self.client_for(self.head).get("/api/inventory-requests").data), 0)   # chỉ thấy của mình

        res = manager.patch(f"/api/inventory-items/{feed}", {"Status": "Inactive"}, format="json")
        self.assertEqual(res.data["Status"], "Inactive")
        res = groom.post("/api/inventory-requests", {"Items": [{"InventoryItemID": feed, "RequestedQuantity": 1}]},
                         format="json")
        self.assertEqual(res.status_code, 400)
        res = manager.patch(f"/api/inventory-items/{feed}", {"Reactivate": True}, format="json")
        self.assertEqual(res.data["Status"], "Available")
        self.assertEqual(self.client_for(self.other_manager).get("/api/inventory-items").data, [])
