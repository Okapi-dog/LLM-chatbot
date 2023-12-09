from pprint import pprint
from typing import Final

import boto3
from boto3.dynamodb.conditions import And, Attr

TABLE_NAME: Final = "ScrapingPhoneStatus"


class ScrapingPhoneStatus:
    def __init__(self, table_name: str) -> None:
        self.dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        self.table = self.dynamodb.Table(table_name)

    def search_text_data(self, request_dict: dict[str, str]) -> list[dict[str, str]]:
        # 初期の条件を作成
        filter_expression = Attr(next(iter(request_dict.keys()))).eq(next(iter(request_dict.values())))
        # 残りの要望を条件に追加
        for key, value in list(request_dict.items())[1:]:
            filter_expression = And(filter_expression, Attr(key).eq(value))
        # 条件に合うデータを検索
        response = self.table.scan(FilterExpression=filter_expression)
        return response["Items"]


if __name__ == "__main__":
    request_dict = {"機種": "Xperia 10 V SIMフリー", "\nCPUコア数\n": ""}  # 要望データの例
    text_db = ScrapingPhoneStatus(TABLE_NAME)
    phone_data = text_db.search_text_data(request_dict)
    pprint(phone_data)
    print("---------------------------------------------------")
