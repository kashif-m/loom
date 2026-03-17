'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import { ArrowLeft, FileText } from 'lucide-react';
import Navigation from '../../../components/Navigation';
import PageHeader from '../../../components/PageHeader';
import StatusBadge from '../../../components/StatusBadge';
import LoadingSpinner from '../../../components/LoadingSpinner';
import ErrorMessage from '../../../components/ErrorMessage';
import { getWorkflow } from '../../../lib/api';

export default function WorkflowDetail() {
  const params = useParams();
  const workflowId = decodeURIComponent(params.workflow_id as string);

  const { data: workflow, isLoading, error } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => getWorkflow(workflowId),
  });

  if (isLoading) {
    return (
      <div>
        <Navigation />
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex justify-center py-12">
            <LoadingSpinner />
          </div>
        </main>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div>
        <Navigation />
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <ErrorMessage message="Failed to load workflow" />
          <div className="mt-4">
            <Link href="/workflows" className="text-amber-600 hover:text-amber-900">
              ← Back to workflows
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div>
      <Navigation />
      
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <Link 
            href="/workflows" 
            className="text-sm text-amber-600 hover:text-amber-900 flex items-center"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to workflows
          </Link>
        </div>

        <PageHeader title={workflow.id} />

        {/* Status Banner */}
        {workflow.status === 'draft' && (
          <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4">
            <p className="text-sm text-amber-800">
              This workflow is pending approval. It will not be used for task matching until approved.
            </p>
          </div>
        )}

        {/* Metadata */}
        <div className="bg-white shadow rounded-lg mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Workflow Details</h2>
          </div>
          <div className="px-6 py-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">ID:</span>
              <span className="ml-2 font-medium">{workflow.id}</span>
            </div>
            <div>
              <span className="text-gray-500">Version:</span>
              <span className="ml-2 font-medium">{workflow.version}</span>
            </div>
            <div>
              <span className="text-gray-500">Level:</span>
              <span className="ml-2 font-medium capitalize">{workflow.level}</span>
            </div>
            <div>
              <span className="text-gray-500">Status:</span>
              <span className="ml-2">
                <StatusBadge status={workflow.status} />
              </span>
            </div>
          </div>
        </div>

        {/* States */}
        <div className="bg-white shadow rounded-lg mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">States</h3>
          </div>
          <div className="px-6 py-4">
            <ol className="relative border-l border-gray-200 ml-3">
              {workflow.states.map((state, idx) => (
                <li key={state} className="mb-6 ml-6">
                  <span className="absolute flex items-center justify-center w-6 h-6 bg-amber-100 rounded-full -left-3 ring-4 ring-white">
                    <span className="text-xs font-medium text-amber-800">{idx + 1}</span>
                  </span>
                  <h4 className="flex items-center mb-1 text-base font-semibold text-gray-900">
                    {state}
                  </h4>
                </li>
              ))}
            </ol>
          </div>
        </div>

        {/* Conditions */}
        <div className="bg-white shadow rounded-lg mb-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Conditions</h3>
          </div>
          <div className="px-6 py-4 space-y-4">
            <div>
              <h4 className="text-sm font-medium text-gray-700">Success Condition</h4>
              <p className="mt-1 text-sm text-gray-600">{workflow.success_condition}</p>
            </div>
            <div>
              <h4 className="text-sm font-medium text-gray-700">Escalate If</h4>
              <p className="mt-1 text-sm text-gray-600">{workflow.escalate_if}</p>
            </div>
          </div>
        </div>

        {/* Tags */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Tags</h3>
          </div>
          <div className="px-6 py-4">
            <div className="flex flex-wrap gap-2">
              {workflow.tags.map(tag => (
                <span 
                  key={tag}
                  className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
