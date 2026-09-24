import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

afterEach(() => {
  cleanup()
  document.documentElement.classList.remove('dark')
})

describe('shared dropdown dark-mode styling', () => {
  it('uses theme-aware trigger, surface, and option states for selects', () => {
    document.documentElement.classList.add('dark')
    render(
      <Select open value="food">
        <SelectTrigger aria-label="Category"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="food">Food</SelectItem>
        </SelectContent>
      </Select>,
    )

    const selectContent = screen.getByRole('listbox')
    const selectItem = screen.getByRole('option', { name: 'Food' })
    expect(document.querySelector('button[aria-label="Category"]')).toHaveClass('bg-background', 'text-foreground')
    expect(selectContent).toHaveClass('bg-popover', 'text-popover-foreground', 'border-border')
    expect(selectItem).toHaveClass(
      'text-popover-foreground', 'data-[highlighted]:bg-accent', 'data-[highlighted]:text-accent-foreground',
      'data-[state=checked]:bg-secondary', 'data-[state=checked]:text-secondary-foreground',
    )
  })

  it('uses theme-aware surface and option states for dropdown menus', () => {
    document.documentElement.classList.add('dark')
    render(
      <DropdownMenu open>
        <DropdownMenuTrigger>Group selector</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Home</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    )
    const menuContent = screen.getByRole('menu')
    const menuItem = screen.getByRole('menuitem', { name: 'Home' })

    expect(menuContent).toHaveClass('bg-popover', 'text-popover-foreground', 'border-border')
    expect(menuItem).toHaveClass('text-popover-foreground', 'data-[highlighted]:bg-accent', 'data-[highlighted]:text-accent-foreground')
  })
})
