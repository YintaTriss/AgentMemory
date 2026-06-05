import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;
  if (diffHour < 24) return `${diffHour} 小时前`;
  if (diffDay < 7) return `${diffDay} 天前`;
  return formatDate(d);
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

export function getCategoryTierLabel(tier: string): string {
  const labels: Record<string, string> = {
    'A': '项目',
    'B': '个人',
    'C': '知识',
  };
  return labels[tier] || tier;
}

export function getCategoryTierColor(tier: string): string {
  const colors: Record<string, string> = {
    'A': 'bg-blue-100 text-blue-800',
    'B': 'bg-green-100 text-green-800',
    'C': 'bg-purple-100 text-purple-800',
  };
  return colors[tier] || 'bg-gray-100 text-gray-800';
}

export function getEmbeddingStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    generating: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    permanent_failure: 'bg-gray-100 text-gray-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}

export function getEmbeddingStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '等待中',
    generating: '生成中',
    completed: '已完成',
    failed: '失败',
    permanent_failure: '永久失败',
  };
  return labels[status] || status;
}

export function getImportanceColor(importance: number): string {
  if (importance >= 0.8) return 'text-red-600';
  if (importance >= 0.6) return 'text-orange-600';
  if (importance >= 0.4) return 'text-yellow-600';
  return 'text-gray-600';
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
