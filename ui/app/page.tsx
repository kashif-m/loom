'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { AlertTriangle, CheckSquare, Clock, FileText } from 'lucide-react';
import Navigation from '../components/Navigation';
import PageHeader from '../components/PageHeader';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import EmptyState from '../components/EmptyState';
import { getTasks, getTaskSummary } from '../lib/api';
import { Task } from '../lib/types';
import { formatDistanceToNow } from 'date-fns';

export default function Dashboard() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['taskSummary'],
    queryFn: getTaskSummary,
  });

  const { data: tasksData, isLoading: tasksLoading, error } = useQuery({
    queryKey: ['recentTasks'],
    queryFn: () => getTasks(undefined, undefined, 20),
  });

  const escalatedTasks = tasksData?.tasks.filter(t => t.status === 'escalated') || [];

  return (
    <div>
      <Navigation />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <PageHeader 
          title="Dashboard" 
          subtitle="Overview of your organisation's task orchestration"
        />

        {/* Escalation Banner */}
        {escalatedTasks.length > 0 && (
          <div className="mb-8 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center">
              <AlertTriangle className="h-5 w-5 text-red-400" />
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">
                  {escalatedTasks.length} task{escalatedTasks.length > 1 ? 's' : ''} need your input
                </h3>
                <p className="mt-1 text-sm text-red-700">
                  <Link href="/tasks" className="font-medium underline">
                    View escalated tasks
                  </Link>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-3 mb-8">
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <Clock className="h-6 w-6 text-blue-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Open Tasks</dt>
                    <dd className="text-2xl font-semibold text-gray-900">
                      {summaryLoading ? '-' : summary?.open || 0}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <AlertTriangle className="h-6 w-6 text-amber-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Blocked</dt>
                    <dd className="text-2xl font-semibold text-gray-900">
                      {summaryLoading ? '-' : summary?.blocked || 0}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <CheckSquare className="h-6 w-6 text-green-400" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">Completed Today</dt>
                    <dd className="text-2xl font-semibold text-gray-900">
                      {summaryLoading ? '-' : summary?.completed_today || 0}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Tasks */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
            <h3 className="text-lg leading-6 font-medium text-gray-900">Recent Tasks</h3>
          </div>
          
          {tasksLoading ? (
            <div className="p-8 flex justify-center">
              <LoadingSpinner />
            </div>
          ) : error ? (
            <div className="p-4">
              <ErrorMessage message="Failed to load tasks" />
            </div>
          ) : tasksData?.tasks.length === 0 ? (
            <EmptyState
              icon={<FileText className="h-12 w-12" />}
              title="No tasks yet"
              description="Submit your first task to get started"
            />
          ) : (
            <div className="overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Task
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Team
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Updated
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {tasksData?.tasks.slice(0, 10).map((task: Task) => (
                    <tr key={task.task_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Link 
                          href={`/tasks/${task.task_id}`}
                          className="text-sm font-medium text-amber-600 hover:text-amber-900"
                        >
                          {task.description.substring(0, 50)}
                          {task.description.length > 50 ? '...' : ''}
                        </Link>
                        <div className="text-xs text-gray-500 mt-1">{task.task_id.substring(0, 8)}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <StatusBadge status={task.status} />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {task.team_id}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDistanceToNow(new Date(task.updated_at), { addSuffix: true })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
