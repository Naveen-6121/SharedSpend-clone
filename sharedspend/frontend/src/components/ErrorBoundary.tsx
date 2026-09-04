import React from 'react'
import { Button } from '@/components/ui/button'

interface State { hasError: boolean; message: string }

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  State
> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="flex flex-col items-center justify-center h-[60vh] gap-4 text-center p-8">
          <p className="text-2xl font-bold text-destructive">Something went wrong</p>
          <p className="text-sm text-muted-foreground max-w-sm">{this.state.message}</p>
          <Button onClick={() => this.setState({ hasError: false, message: '' })}>Try again</Button>
        </div>
      )
    }
    return this.props.children
  }
}
