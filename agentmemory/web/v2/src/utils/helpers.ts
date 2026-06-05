import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import type { EmbeddingStatus } from '@/types';

// Tailwind 类名合并
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// 日期格式化
export function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return format(date, 'yyyy-MM-dd HH:mm:ss', { locale: zhCN });
  } catch {
    return dateString;
  }
}

export function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    return formatDistanceToNow(date, { addSuffix: true, locale: zhCN });
  } catch {
    return dateString;
  }
}

// 文件大小格式化
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Embedding 状态标签和颜色
export function getEmbeddingStatusConfig(status: EmbeddingStatus): { 
  label: string; 
  color: string; 
  bgColor: string;
  icon: string;
} {
  const configs: Record<EmbeddingStatus, { label: string; color: string; bgColor: string; icon: string }> = {
    pending: { label: '待处理', color: 'text-gray-600', bgColor: 'bg-gray-100', icon: '⏳' },
    generating: { label: '生成中', color: 'text-blue-600', bgColor: 'bg-blue-100', icon: '🔄' },
    completed: { label: '已完成', color: 'text-green-600', bgColor: 'bg-green-100', icon: '✅' },
    failed: { label: '失败', color: 'text-orange-600', bgColor: 'bg-orange-100', icon: '⚠️' },
    permanent_failure: { label: '永久失败', color: 'text-red-600', bgColor: 'bg-red-100', icon: '❌' },
  };
  return configs[status];
}

// 生成唯一 ID
export function generateId(prefix: string = 'id'): string {
  const timestamp = Date.now().toString(36);
  const randomStr = Math.random().toString(36).substring(2, 8);
  return prefix + '_' + timestamp + '_' + randomStr;
}

// 截断文本
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

// 高亮搜索关键词
export function highlightText(text: string, query: string): string {
  if (!query) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\]/g, '\$&');
  const regex = new RegExp('(' + escaped + ')', 'gi');
  return text.replace(regex, '<mark class="bg-yellow-200">$1</mark>');
}

// 复制到剪贴板
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// 百分比格式化
export function formatPercentage(value: number, decimals: number = 1): string {
  return (value * 100).toFixed(decimals) + '%';
}

// 速率格式化 (条/分钟)
export function formatRate(rate: number): string {
  if (rate < 0.1) return '<0.1 条/分';
  return rate.toFixed(1) + ' 条/分';
}

// 防抖函数
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

// 节流函数
export function throttle<T extends (...args: unknown[]) => unknown>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => { inThrottle = false; }, limit);
    }
  };
}
