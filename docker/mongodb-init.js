// MongoDB 初始化腳本
print('開始初始化 news_analyze 資料庫...');

// 切換到 news_analyze 資料庫
db = db.getSiblingDB('news_analyze');

// 創建新聞用戶
db.createUser({
  user: 'news_user',
  pwd: 'news_password_2024',
  roles: [
    {
      role: 'readWrite',
      db: 'news_analyze'
    }
  ]
});

// 創建 news 集合（如果不存在）
db.createCollection('news');

// 創建索引
db.news.createIndex({ 'news_source': 1 });
db.news.createIndex({ 'news_id': 1 });
db.news.createIndex({ 'create_time': -1 });
db.news.createIndex({ 'news_source': 1, 'news_id': 1 }, { unique: true });

print('news_analyze 資料庫初始化完成！');
print('創建的索引:');
db.news.getIndexes().forEach(printjson);
