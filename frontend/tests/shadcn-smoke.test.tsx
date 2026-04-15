import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

describe('shadcn/ui components smoke test', () => {
  describe('Button', () => {
    it('renders with children', () => {
      render(<Button>Click me</Button>)
      expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument()
    })
  })

  describe('Input', () => {
    it('renders with placeholder', () => {
      render(<Input placeholder="Enter text" />)
      expect(screen.getByPlaceholderText(/enter text/i)).toBeInTheDocument()
    })
  })

  describe('Switch', () => {
    it('toggles checked state', () => {
      // Render unchecked switch
      const { rerender } = render(<Switch checked={false} onCheckedChange={() => {}} />)
      const switchEl = screen.getByRole('switch')
      expect(switchEl).toHaveAttribute('aria-checked', 'false')

      // Rerender as checked
      rerender(<Switch checked={true} onCheckedChange={() => {}} />)
      expect(switchEl).toHaveAttribute('aria-checked', 'true')
    })
  })

  describe('Badge', () => {
    it('renders with variant', () => {
      render(<Badge variant="secondary">New</Badge>)
      expect(screen.getByText(/new/i)).toBeInTheDocument()
      expect(screen.getByText(/new/i)).toHaveClass('bg-secondary')
    })
  })

  describe('Tooltip', () => {
    it('shows content on hover', async () => {
      const user = userEvent.setup()
      render(
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger>Hover me</TooltipTrigger>
            <TooltipContent>Tooltip content</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )

      const trigger = screen.getByText(/hover me/i)
      expect(screen.queryByText(/tooltip content/i)).not.toBeInTheDocument()

      await user.hover(trigger)
      await waitFor(() => {
        expect(screen.getByText(/tooltip content/i)).toBeInTheDocument()
      })
    })
  })
})
