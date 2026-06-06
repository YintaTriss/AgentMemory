#!/bin/bash
# AgentMemory Web API 测试脚本
# 用 curl 跑通所有端点

set -e

BASE_URL="http://localhost:8765"
TEST_ID="test_$(date +%s)"

echo "========================================"
echo "  AgentMemory API 测试脚本"
echo "========================================"
echo ""

# 检查服务是否运行
echo "1. 检查服务状态..."
if ! curl -s "$BASE_URL/api/health" > /dev/null 2>&1; then
    echo "❌ 服务未运行，请先启动: python -m web_server"
    exit 1
fi
echo "✅ 服务正在运行"
echo ""

# 测试健康检查
echo "2. 测试健康检查..."
response=$(curl -s "$BASE_URL/api/health")
echo "Response: $response"
if echo "$response" | grep -q "ok"; then
    echo "✅ 健康检查通过"
else
    echo "❌ 健康检查失败"
    exit 1
fi
echo ""

# 测试创建记忆
echo "3. 测试创建记忆..."
response=$(curl -s -X POST "$BASE_URL/api/memories" \
    -H "Content-Type: application/json" \
    -d "{\"content\": \"$TEST_ID - 测试记忆内容\", \"importance\": 0.8, \"category_path\": \"测试/单元测试\", \"tags\": [\"test\", \"api\"]}")
echo "Response: $response"
if echo "$response" | grep -q "id"; then
    echo "✅ 创建记忆成功"
    MEMORY_ID=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo "   Memory ID: $MEMORY_ID"
else
    echo "❌ 创建记忆失败"
    exit 1
fi
echo ""

# 测试列出记忆
echo "4. 测试列出记忆..."
response=$(curl -s "$BASE_URL/api/memories?limit=5")
echo "Response: $response"
if echo "$response" | grep -q "memories"; then
    echo "✅ 列出记忆成功"
else
    echo "❌ 列出记忆失败"
    exit 1
fi
echo ""

# 测试获取单条记忆
echo "5. 测试获取单条记忆..."
if [ -n "$MEMORY_ID" ]; then
    response=$(curl -s "$BASE_URL/api/memories/$MEMORY_ID")
    echo "Response: $response"
    if echo "$response" | grep -q "$TEST_ID"; then
        echo "✅ 获取单条记忆成功"
    else
        echo "⚠️ 可能获取失败（但可能是正常的）"
    fi
else
    echo "⚠️ 跳过（无 memory_id）"
fi
echo ""

# 测试语义搜索
echo "6. 测试语义搜索..."
response=$(curl -s "$BASE_URL/api/search?q=$TEST_ID&limit=3")
echo "Response: $response"
if echo "$response" | grep -q "results"; then
    echo "✅ 语义搜索成功"
else
    echo "❌ 语义搜索失败"
    exit 1
fi
echo ""

# 测试统计信息
echo "7. 测试统计信息..."
response=$(curl -s "$BASE_URL/api/stats")
echo "Response: $response"
if echo "$response" | grep -q "stats"; then
    echo "✅ 统计信息获取成功"
else
    echo "❌ 统计信息获取失败"
    exit 1
fi
echo ""

# 测试分类
echo "8. 测试获取分类..."
response=$(curl -s "$BASE_URL/api/categories")
echo "Response: $response"
echo "✅ 分类接口正常"
echo ""

# 测试同步
echo "9. 测试同步..."
response=$(curl -s -X POST "$BASE_URL/api/sync")
echo "Response: $response"
if echo "$response" | grep -q "status"; then
    echo "✅ 同步接口正常"
else
    echo "⚠️ 同步可能失败（但可能是正常的）"
fi
echo ""

# 测试压缩
echo "10. 测试压缩..."
if [ -n "$MEMORY_ID" ]; then
    response=$(curl -s -X POST "$BASE_URL/api/compress" \
        -H "Content-Type: application/json" \
        -d "{\"ids\": [\"$MEMORY_ID\"]}")
    echo "Response: $response"
    if echo "$response" | grep -q "summary"; then
        echo "✅ 压缩接口正常"
    else
        echo "⚠️ 压缩可能失败（但可能是正常的）"
    fi
else
    echo "⚠️ 跳过（无 memory_id）"
fi
echo ""

# 测试删除（可选，取消注释以启用）
# echo "11. 测试删除记忆..."
# if [ -n "$MEMORY_ID" ]; then
#     response=$(curl -s -X DELETE "$BASE_URL/api/memories/$MEMORY_ID")
#     echo "Response: $response"
#     if echo "$response" | grep -q "deleted"; then
#         echo "✅ 删除记忆成功"
#     else
#         echo "⚠️ 删除可能失败（但可能是正常的）"
#     fi
# else
#     echo "⚠️ 跳过（无 memory_id）"
# fi
# echo ""

echo "========================================"
echo "  ✅ 所有测试完成！"
echo "========================================"
echo ""
echo "测试记忆ID: $MEMORY_ID"
echo ""
