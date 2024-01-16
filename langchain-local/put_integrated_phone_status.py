import pickle
from typing import Final

from . import integrate_phone_status  # パスはお好みで

PICKLE_FILE_PATH: Final = "integrated_phone_status.pickle"

if __name__ == "__main__":
    # ファイルからデータを読み込む
    with open(PICKLE_FILE_PATH, "rb") as f:
        integrated_phone_data: list[dict[str, str]] = pickle.load(f)

    # データをDynamoDBに保存
    with integrate_phone_status.DynamoDB("IntegratedPhoneStatus").table.batch_writer() as batch:
        for integrated_phone_dict in integrated_phone_data:
            batch.put_item(Item=integrated_phone_dict)
