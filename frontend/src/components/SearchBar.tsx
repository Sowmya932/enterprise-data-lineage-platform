import { FormEvent, useState } from 'react';

interface SearchBarProps {
  placeholder?: string;
  initialValue?: string;
  submitLabel?: string;
  onSearch: (query: string) => void;
}

function SearchBar({
  placeholder = 'Search...',
  initialValue = '',
  submitLabel = 'Search',
  onSearch,
}: SearchBarProps): JSX.Element {
  const [value, setValue] = useState(initialValue);

  const handleSubmit = (event: FormEvent): void => {
    event.preventDefault();
    onSearch(value.trim());
  };

  return (
    <form className="searchbar" onSubmit={handleSubmit}>
      <label>
        Search
        <input
          type="text"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={placeholder}
        />
      </label>
      <button type="submit" className="searchbar-button">
        {submitLabel}
      </button>
    </form>
  );
}

export default SearchBar;
